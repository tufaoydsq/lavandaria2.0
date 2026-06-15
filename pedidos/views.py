from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json
import io
import os
import base64
import re
import requests
from datetime import timedelta
from django.db import transaction
from django.db.models import Sum, Count, Q, OuterRef, Subquery, Value, DecimalField, F, Prefetch
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.conf import settings
from django.template.loader import render_to_string
from PIL import Image, ImageDraw, ImageFont

from core.decorators import admin_required, vendedor_required
from core.models import (
    Pedido, ItemPedido, Cliente, ItemServico,
    PagamentoPedido, MovimentacaoPontos, Lavandaria, Funcionario
)


# ========== VIEWS PRINCIPAIS ==========

@login_required
@vendedor_required
def ver_pedidos(request):
    """
    View para página de gerenciamento de pedidos
    """
    return render(request, 'pedidos/pedidos.html')


# ========== API DE PEDIDOS ==========

@login_required
@vendedor_required
@csrf_exempt
@require_http_methods(["GET"])
def listar_pedidos(request):
    """
    API: Listar todos os pedidos com filtros (VERSÃO OTIMIZADA)
    """
    try:
        # Filtrar por lavandaria do funcionário
        usuario_logado = request.user
        lavandaria_usuario = None

        if hasattr(usuario_logado, 'funcionario'):
            lavandaria_usuario = usuario_logado.funcionario.lavandaria

        status_filter = request.GET.get('status', '')
        pagamento_filter = request.GET.get('pagamento', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        cliente_search = request.GET.get('cliente', '')
        pedido_id_search = request.GET.get('pedido_id', '')  # 🔥 NOVO
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))

        # Query base
        pedidos = Pedido.objects.select_related('cliente', 'funcionario', 'lavandaria')

        if lavandaria_usuario:
            pedidos = pedidos.filter(lavandaria=lavandaria_usuario)

        # Aplicar filtros
        if status_filter and status_filter != 'all':
            pedidos = pedidos.filter(status=status_filter)

        if pagamento_filter and pagamento_filter != 'all':
            pedidos = pedidos.filter(status_pagamento=pagamento_filter)

        if data_inicio:
            pedidos = pedidos.filter(criado_em__date__gte=data_inicio)

        if data_fim:
            pedidos = pedidos.filter(criado_em__date__lte=data_fim)

        if cliente_search:
            pedidos = pedidos.filter(cliente__nome__icontains=cliente_search)

        # 🔥 NOVO FILTRO: Buscar por ID do pedido
        if pedido_id_search:
            # Verificar se é um número
            if pedido_id_search.isdigit():
                pedidos = pedidos.filter(id=int(pedido_id_search))
            else:
                # Tentar extrair número do formato #123456
                import re
                match = re.search(r'\d+', pedido_id_search)
                if match:
                    pedidos = pedidos.filter(id=int(match.group()))

        # Ordenar e anotar totais
        pedidos = pedidos.order_by('-criado_em')
        pedidos = pedidos.annotate(total_itens=Sum('itens__quantidade'))

        # Paginação
        total_pedidos = pedidos.count()
        start = (page - 1) * per_page
        end = start + per_page
        pedidos_paginados = pedidos[start:end]

        # Prefetch relacionamentos
        pedidos_paginados = pedidos_paginados.prefetch_related(
            Prefetch('itens', queryset=ItemPedido.objects.select_related('item_de_servico'))
        )

        pedidos_data = []
        for pedido in pedidos_paginados:
            total_itens = pedido.total_itens or 0

            pedidos_data.append({
                'id': pedido.id,
                'id_formatado': f'#{pedido.id:06d}',
                'cliente_id': pedido.cliente.id,
                'cliente_nome': pedido.cliente.nome,
                'cliente_telefone': pedido.cliente.telefone or '',
                'itens': total_itens,
                'total': float(pedido.total),
                'desconto': float(pedido.desconto),
                'desconto_cabides': float(pedido.desconto_cabides),
                'total_final': float(pedido.total_final),
                'total_pago': float(pedido.total_pago),
                'saldo': float(pedido.saldo),
                'status': pedido.status,
                'status_label': dict(Pedido.STATUS_CHOICES).get(pedido.status),
                'status_pagamento': pedido.status_pagamento,
                'status_pagamento_label': dict(Pedido.STATUS_PAGAMENTO_CHOICES).get(pedido.status_pagamento),
                'cabides_trazidos': pedido.cabides_trazidos,
                'criado_em': pedido.criado_em.strftime('%d/%m/%Y %H:%M'),
                'funcionario': pedido.funcionario.user.get_full_name() if pedido.funcionario else '—',
            })

        return JsonResponse({
            'success': True,
            'pedidos': pedidos_data,
            'total': total_pedidos,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_pedidos + per_page - 1) // per_page
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@vendedor_required
@csrf_exempt
@require_http_methods(["GET"])
def detalhes_pedido(request, id):
    """
    API: Obter detalhes de um pedido específico
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)

        # Verificar permissão
        usuario_logado = request.user
        if hasattr(usuario_logado, 'funcionario'):
            lavandaria_usuario = usuario_logado.funcionario.lavandaria
            if lavandaria_usuario and pedido.lavandaria != lavandaria_usuario:
                return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)

        # Itens do pedido com descrição
        itens = []
        for item in pedido.itens.all():
            itens.append({
                'id': item.id,
                'nome': item.item_de_servico.nome if item.item_de_servico else 'Item',
                'quantidade': item.quantidade,
                'preco_unitario': float(item.item_de_servico.preco_base) if item.item_de_servico else 0,
                'preco_total': float(item.preco_total),
                'descricao': item.descricao or ''
            })

        # Pagamentos
        pagamentos = []
        for pag in pedido.pagamentos.all():
            pagamentos.append({
                'id': pag.id,
                'valor': float(pag.valor),
                'metodo': pag.get_metodo_pagamento_display(),
                'data': pag.pago_em.strftime('%d/%m/%Y %H:%M'),
                'referencia': pag.referencia or ''
            })

        return JsonResponse({
            'success': True,
            'pedido': {
                'id': pedido.id,
                'cliente_nome': pedido.cliente.nome,
                'cliente_telefone': pedido.cliente.telefone,
                'cliente_pontos': pedido.cliente.pontos,
                'itens': itens,
                'pagamentos': pagamentos,
                'subtotal': float(pedido.total),
                'desconto_fidelidade': float(pedido.desconto),
                'desconto_cabides': float(pedido.desconto_cabides),
                'cabides_trazidos': pedido.cabides_trazidos,
                'total_final': float(pedido.total_final),
                'total_pago': float(pedido.total_pago),
                'saldo': float(pedido.saldo),
                'status': pedido.status,
                'status_label': dict(Pedido.STATUS_CHOICES).get(pedido.status),
                'status_pagamento': pedido.status_pagamento,
                'status_pagamento_label': dict(Pedido.STATUS_PAGAMENTO_CHOICES).get(pedido.status_pagamento),
                'criado_em': pedido.criado_em.strftime('%d/%m/%Y %H:%M'),
                'funcionario': pedido.funcionario.user.get_full_name() if pedido.funcionario else '—'
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@vendedor_required
@csrf_exempt
@require_http_methods(["GET"])
def listar_clientes(request):
    """
    API: Listar clientes para o select
    """
    clientes = Cliente.objects.all().values('id', 'nome', 'telefone')
    return JsonResponse({'success': True, 'clientes': list(clientes)})


@login_required
@vendedor_required
@csrf_exempt
@require_http_methods(["GET"])
def listar_artigos(request):
    """
    API: Listar artigos disponíveis
    """
    artigos = ItemServico.objects.filter(disponivel=True).values('id', 'nome', 'preco_base')
    return JsonResponse({'success': True, 'artigos': list(artigos)})


@login_required
@vendedor_required
@csrf_exempt
@require_http_methods(["POST"])
def criar_pedido(request):
    """
    API: Criar novo pedido
    """
    try:
        data = json.loads(request.body)

        cliente_id = data.get('cliente_id')
        cabides_trazidos = data.get('cabides_trazidos', 0)
        itens = data.get('itens', [])

        if not cliente_id:
            return JsonResponse({'success': False, 'error': 'Cliente é obrigatório'}, status=400)
        if not itens:
            return JsonResponse({'success': False, 'error': 'Adicione pelo menos um item'}, status=400)

        cliente = get_object_or_404(Cliente, id=cliente_id)

        # Obter lavandaria do funcionário
        lavandaria = None
        funcionario = None
        if hasattr(request.user, 'funcionario'):
            funcionario = request.user.funcionario
            lavandaria = funcionario.lavandaria

        # Criar pedido
        pedido = Pedido.objects.create(
            cliente=cliente,
            lavandaria=lavandaria,
            funcionario=funcionario,
            cabides_trazidos=cabides_trazidos,
            status='pendente',
            status_pagamento='nao_pago'
        )

        # Adicionar itens com descrição
        for item_data in itens:
            artigo_id = item_data.get('artigo_id')
            quantidade = item_data.get('quantidade', 1)
            descricao = item_data.get('descricao', '')

            artigo = get_object_or_404(ItemServico, id=artigo_id)

            ItemPedido.objects.create(
                pedido=pedido,
                item_de_servico=artigo,
                quantidade=quantidade,
                descricao=descricao
            )

        pedido.atualizar_total()

        return JsonResponse({
            'success': True,
            'message': 'Pedido criado com sucesso!',
            'pedido_id': pedido.id
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@admin_required
@csrf_exempt
@require_http_methods(["PUT"])
def editar_pedido(request, id):
    """
    API: Editar pedido existente
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)

        # Verificar permissão
        usuario_logado = request.user
        if hasattr(usuario_logado, 'funcionario'):
            lavandaria_usuario = usuario_logado.funcionario.lavandaria
            if lavandaria_usuario and pedido.lavandaria != lavandaria_usuario:
                return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)

        data = json.loads(request.body)

        if 'cabides_trazidos' in data:
            pedido.cabides_trazidos = data['cabides_trazidos']
            pedido.desconto_cabides = pedido.calcular_desconto_cabides()

        if 'status' in data:
            pedido.status = data['status']

        pedido.save()

        return JsonResponse({
            'success': True,
            'message': 'Pedido atualizado com sucesso!'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@vendedor_required
@csrf_exempt
@require_http_methods(["POST"])
@transaction.atomic
def registrar_pagamento(request, id):
    """
    API: Registrar pagamento de um pedido
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)

        # Verificar permissão
        usuario_logado = request.user
        if hasattr(usuario_logado, 'funcionario'):
            lavandaria_usuario = usuario_logado.funcionario.lavandaria
            if lavandaria_usuario and pedido.lavandaria != lavandaria_usuario:
                return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)

        data = json.loads(request.body)

        valor = Decimal(str(data.get('valor', 0)))
        metodo = data.get('metodo')
        referencia = data.get('referencia', '')

        if valor <= 0:
            return JsonResponse({'success': False, 'error': 'Valor do pagamento deve ser maior que zero'}, status=400)

        if valor > pedido.saldo:
            return JsonResponse({'success': False, 'error': f'Valor excede o saldo pendente de {pedido.saldo} MT'},
                                status=400)

        funcionario = None
        if hasattr(request.user, 'funcionario'):
            funcionario = request.user.funcionario

        PagamentoPedido.objects.create(
            pedido=pedido,
            valor=valor,
            metodo_pagamento=metodo,
            referencia=referencia,
            criado_por=funcionario
        )

        pedido.recalcular_pagamentos()

        return JsonResponse({
            'success': True,
            'message': f'Pagamento de {valor} MT registrado com sucesso!',
            'saldo_restante': float(pedido.saldo)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@vendedor_required
@csrf_exempt
@require_http_methods(["PATCH"])
def atualizar_status_pedido(request, id):
    """
    API: Atualizar o status do pedido com validação de fluxo
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)

        # Verificar permissão
        usuario_logado = request.user
        if hasattr(usuario_logado, 'funcionario'):
            lavandaria_usuario = usuario_logado.funcionario.lavandaria
            if lavandaria_usuario and pedido.lavandaria != lavandaria_usuario:
                return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            return JsonResponse({'success': False, 'error': f'JSON inválido: {str(e)}'}, status=400)

        novo_status = data.get('status')

        if not novo_status:
            return JsonResponse({'success': False, 'error': 'Status não informado'}, status=400)

        STATUS_VALIDOS = ['pendente', 'completo', 'pronto', 'entregue']

        if novo_status not in STATUS_VALIDOS:
            return JsonResponse({
                'success': False,
                'error': f'Status inválido: {novo_status}'
            }, status=400)

        status_atual = pedido.status

        if status_atual == novo_status:
            return JsonResponse({
                'success': False,
                'error': f'O pedido já está como {novo_status}'
            }, status=400)

        transicoes_permitidas = {
            'pendente': ['completo'],
            'completo': ['pronto'],
            'pronto': ['entregue'],
            'entregue': []
        }

        if novo_status not in transicoes_permitidas.get(status_atual, []):
            return JsonResponse({
                'success': False,
                'error': f'Transição inválida! Não é possível alterar de "{status_atual}" para "{novo_status}".'
            }, status=400)

        if novo_status == 'entregue' and pedido.saldo > 0:
            return JsonResponse({
                'success': False,
                'error': f'Não é possível entregar o pedido pois há saldo pendente de {float(pedido.saldo):.2f} MT'
            }, status=400)

        pedido.status = novo_status
        pedido.save()

        return JsonResponse({
            'success': True,
            'message': f'Status do pedido #{pedido.id} atualizado para {novo_status}!',
            'status': novo_status,
            'status_label': novo_status.capitalize()
        })

    except Pedido.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Pedido não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@admin_required
@csrf_exempt
@require_http_methods(["DELETE"])
def excluir_pedido(request, id):
    """
    API: Excluir pedido
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)

        # Verificar permissão
        usuario_logado = request.user
        if hasattr(usuario_logado, 'funcionario'):
            lavandaria_usuario = usuario_logado.funcionario.lavandaria
            if lavandaria_usuario and pedido.lavandaria != lavandaria_usuario:
                return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)

        if pedido.status_pagamento == 'pago':
            return JsonResponse({'success': False, 'error': 'Não é possível excluir um pedido já pago'}, status=400)

        pedido.delete()

        return JsonResponse({
            'success': True,
            'message': 'Pedido excluído com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ========== RECIBO TÉRMICO ==========

@login_required
@vendedor_required
def recibo_termico_view(request, id):
    """
    View para gerar página HTML do recibo térmico
    """
    pedido = get_object_or_404(Pedido, id=id)
    if hasattr(request.user, 'funcionario') and pedido.lavandaria != request.user.funcionario.lavandaria:
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)

    pagos_subq = (
        PagamentoPedido.objects
        .filter(pedido=OuterRef("pk"))
        .values("pedido")
        .annotate(s=Sum("valor"))
        .values("s")[:1]
    )

    pedidos_nao_pagos = (
        Pedido.objects
        .filter(cliente=pedido.cliente)
        .exclude(status_pagamento="pago")
        .annotate(
            valor_pago_calc=Coalesce(
                Subquery(pagos_subq),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .annotate(
            saldo_calc=Coalesce(
                F("total") - F("valor_pago_calc"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("-criado_em")
    )[:3]

    total_em_divida = (
        Pedido.objects
        .filter(cliente=pedido.cliente)
        .exclude(status_pagamento="pago")
        .annotate(
            valor_pago_calc=Coalesce(
                Subquery(pagos_subq),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .annotate(
            saldo_calc=Coalesce(
                F("total") - F("valor_pago_calc"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .aggregate(
            total=Coalesce(
                Sum("saldo_calc"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    )

    valor_pago = (
        PagamentoPedido.objects
        .filter(pedido=pedido)
        .aggregate(
            total=Coalesce(
                Sum("valor"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    )

    desconto_aplicado = pedido.desconto or Decimal("0.00")
    saldo = pedido.saldo

    mov_pontos = MovimentacaoPontos.objects.filter(pedido=pedido, tipo="ganho").first()
    pontos_ganhos = mov_pontos.pontos if mov_pontos else 0
    pontos_totais = pedido.cliente.pontos
    data_validade_pontos = pedido.criado_em + timedelta(days=90)

    context = {
        'pedido': pedido,
        'pedidos_nao_pagos': pedidos_nao_pagos,
        'total_em_divida': total_em_divida,
        'valor_pago': valor_pago,
        'saldo': saldo,
        'desconto_aplicado': desconto_aplicado,
        'pontos_ganhos': pontos_ganhos,
        'pontos_totais': pontos_totais,
        'data_validade_pontos': data_validade_pontos,
    }

    return render(request, 'pedidos/recibo_termico.html', context)



@login_required
@vendedor_required
def imprimir_recibo_imagem(request, id):
    """
    API: Gerar imagem do recibo térmico
    """
    pedido = get_object_or_404(Pedido, id=id)
    if hasattr(request.user, 'funcionario') and pedido.lavandaria != request.user.funcionario.lavandaria:
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)

    pagos_subq = (
        PagamentoPedido.objects
        .filter(pedido=OuterRef("pk"))
        .values("pedido")
        .annotate(s=Sum("valor"))
        .values("s")[:1]
    )

    pedidos_nao_pagos = (
        Pedido.objects
        .filter(cliente=pedido.cliente)
        .exclude(status_pagamento="pago")
        .annotate(
            valor_pago_calc=Coalesce(
                Subquery(pagos_subq),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .annotate(
            saldo_calc=Coalesce(
                F("total") - F("valor_pago_calc"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("-criado_em")
    )[:3]

    total_em_divida = (
        Pedido.objects
        .filter(cliente=pedido.cliente)
        .exclude(status_pagamento="pago")
        .annotate(
            valor_pago_calc=Coalesce(
                Subquery(pagos_subq),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .annotate(
            saldo_calc=Coalesce(
                F("total") - F("valor_pago_calc"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .aggregate(
            total=Coalesce(
                Sum("saldo_calc"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    )

    valor_pago = (
        PagamentoPedido.objects
        .filter(pedido=pedido)
        .aggregate(
            total=Coalesce(
                Sum("valor"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    )

    desconto_aplicado = pedido.desconto or Decimal("0.00")
    saldo = pedido.saldo

    mov_pontos = MovimentacaoPontos.objects.filter(pedido=pedido, tipo="ganho").first()
    pontos_ganhos = mov_pontos.pontos if mov_pontos else 0
    pontos_totais = pedido.cliente.pontos
    data_validade_pontos = pedido.criado_em + timedelta(days=90)

    recibo_texto = render_to_string("pedidos/recibo_termico.txt", {
        "pedido": pedido,
        "pedidos_nao_pagos": pedidos_nao_pagos,
        "total_em_divida": total_em_divida,
        "valor_pago": valor_pago,
        "saldo": saldo,
        "desconto_aplicado": desconto_aplicado,
        "pontos_ganhos": pontos_ganhos,
        "pontos_totais": pontos_totais,
        "data_validade_pontos": data_validade_pontos,
    })

    try:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", 10)
        except:
            font = ImageFont.load_default()

        largura = 400
        altura_texto = 0
        draw = ImageDraw.Draw(Image.new("RGB", (largura, 1)))

        for linha in recibo_texto.split("\n"):
            bbox = draw.textbbox((0, 0), linha, font=font)
            altura_linha = bbox[3] - bbox[1]
            altura_texto += altura_linha + 4

        espaco_logo = 80
        altura = max(altura_texto + espaco_logo, 200)

        img = Image.new("RGB", (largura, altura), "white")
        draw = ImageDraw.Draw(img)

        # Logo (opcional)
        try:
            logo_path = os.path.join(settings.BASE_DIR, "static/img/logo.jpg")
            if os.path.exists(logo_path):
                logo = Image.open(logo_path).convert("RGBA")
                logo = logo.resize((120, 60))
                x_logo = (largura - logo.width) // 2
                img.paste(logo, (x_logo, 10), logo)
        except Exception:
            pass

        draw.multiline_text(
            (10, espaco_logo),
            recibo_texto,
            fill="black",
            font=font,
            spacing=4
        )

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return render(request, "pedidos/imprimir_recibo.html", {"img_base64": img_base64})

    except ImportError:
        return render(request, 'pedidos/recibo_termico.html', {
            "pedido": pedido,
            "pedidos_nao_pagos": pedidos_nao_pagos,
            "total_em_divida": total_em_divida,
            "valor_pago": valor_pago,
            "saldo": saldo,
            "desconto_aplicado": desconto_aplicado,
            "pontos_ganhos": pontos_ganhos,
            "pontos_totais": pontos_totais,
            "data_validade_pontos": data_validade_pontos,
        })


# ========== SMS ==========

SMS_API_URL = 'https://api.mozesms.com/v2/sms/bulk'
SMS_BEARER_TOKEN = 'Bearer 2374:zKNUpX-J4dao9-VEi60O-UeNqdN'
SMS_SENDER_ID = "POWERWASH"


def enviar_sms_mozesms(numero, mensagem, pedido=None, cliente=None):
    """
    Envia um SMS usando a API Mozesms
    """
    numero_limpo = re.sub(r'\D', '', numero)

    if len(numero_limpo) == 9:
        numero_limpo = '258' + numero_limpo
    elif len(numero_limpo) == 12 and numero_limpo.startswith('258'):
        pass
    else:
        numero_limpo = '258' + numero_limpo

    if len(numero_limpo) != 12:
        return False, f"Número inválido: {numero}"

    payload = {
        'sender_id': SMS_SENDER_ID,
        'messages': [{'phone': numero_limpo, 'message': mensagem}]
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': SMS_BEARER_TOKEN
    }

    try:
        response = requests.post(SMS_API_URL, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            try:
                json_resposta = response.json()
                if json_resposta.get('success') or json_resposta.get('status') == 'success':
                    return True, json_resposta
                else:
                    erro_msg = json_resposta.get('message', json_resposta.get('error', 'Erro desconhecido'))
                    return False, erro_msg
            except Exception as e:
                return False, str(e)
        else:
            return False, f"HTTP {response.status_code}"

    except requests.RequestException as e:
        return False, str(e)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
@vendedor_required
def enviar_sms_pedido_pronto(request, pedido_id):
    """
    API: Enviar SMS notificando que o pedido está pronto
    """
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        if hasattr(request.user, 'funcionario') and pedido.lavandaria != request.user.funcionario.lavandaria:
            return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)
        cliente = pedido.cliente

        if pedido.status != 'pronto':
            return JsonResponse({
                'success': False,
                'error': f'O pedido não está com status "Pronto". Status atual: {pedido.get_status_display()}'
            }, status=400)

        if not cliente.telefone:
            return JsonResponse({
                'success': False,
                'error': 'Cliente não possui número de telefone cadastrado'
            }, status=400)

        lavandaria = pedido.lavandaria

        mensagem = f"""🏷 POWERWASH - Pedido Pronto!

Olá {cliente.nome},
Seu pedido #{pedido.id} está PRONTO para retirada!

{lavandaria.endereco}
Contato: {lavandaria.telefone}

⚠Você tem 30 dias para retirar.
Após este prazo, será aplicada taxa de armazenamento.

Obrigado pela preferência! """

        sucesso, resposta = enviar_sms_mozesms(cliente.telefone, mensagem, pedido, cliente)

        if sucesso:
            return JsonResponse({
                'success': True,
                'message': f'SMS enviado com sucesso para {cliente.nome} ({cliente.telefone})'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Falha ao enviar SMS: {resposta}'
            }, status=500)

    except Pedido.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Pedido não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


