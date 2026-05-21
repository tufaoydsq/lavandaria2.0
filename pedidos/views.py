from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json
from core.models import Pedido, ItemPedido, Cliente, ItemServico, PagamentoPedido, MovimentacaoPontos
from core.models import Lavandaria
from core.models import Funcionario
from django.db.models import Sum, Q, Count
from django.db import transaction


def ver_pedidos(request):
    """
    View para página de gerenciamento de pedidos
    """
    return render(request, 'pedidos/pedidos.html')


@csrf_exempt
@require_http_methods(["GET"])
def listar_pedidos(request):
    """
    API: Listar todos os pedidos com filtros
    """
    status_filter = request.GET.get('status', '')
    pagamento_filter = request.GET.get('pagamento', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    cliente_search = request.GET.get('cliente', '')

    pedidos = Pedido.objects.select_related('cliente', 'funcionario', 'lavandaria').all()

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

    pedidos_data = []
    for pedido in pedidos.order_by('-criado_em'):
        total_itens = pedido.itens.aggregate(total=Sum('quantidade'))['total'] or 0

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

    return JsonResponse({'success': True, 'pedidos': pedidos_data})


@csrf_exempt
@require_http_methods(["GET"])
def detalhes_pedido(request, id):
    """
    API: Obter detalhes de um pedido específico
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)

        # Itens do pedido
        itens = []
        for item in pedido.itens.all():
            itens.append({
                'id': item.id,
                'nome': item.item_de_servico.nome if item.item_de_servico else 'Item',
                'quantidade': item.quantidade,
                'preco_unitario': float(item.item_de_servico.preco_base) if item.item_de_servico else 0,
                'preco_total': float(item.preco_total)
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


@csrf_exempt
@require_http_methods(["GET"])
def listar_clientes(request):
    """
    API: Listar clientes para o select
    """
    clientes = Cliente.objects.all().values('id', 'nome', 'telefone')
    return JsonResponse({'success': True, 'clientes': list(clientes)})


@csrf_exempt
@require_http_methods(["GET"])
def listar_artigos(request):
    """
    API: Listar artigos disponíveis
    """
    artigos = ItemServico.objects.filter(disponivel=True).values('id', 'nome', 'preco_base')
    return JsonResponse({'success': True, 'artigos': list(artigos)})


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

        # Obter lavandaria do funcionário logado
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

        # Adicionar itens
        for item_data in itens:
            artigo_id = item_data.get('artigo_id')
            quantidade = item_data.get('quantidade', 1)

            artigo = get_object_or_404(ItemServico, id=artigo_id)

            ItemPedido.objects.create(
                pedido=pedido,
                item_de_servico=artigo,
                quantidade=quantidade
            )

        # Atualizar total e descontos
        pedido.atualizar_total()

        return JsonResponse({
            'success': True,
            'message': 'Pedido criado com sucesso!',
            'pedido_id': pedido.id
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
def editar_pedido(request, id):
    """
    API: Editar pedido existente
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)
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


@csrf_exempt
@require_http_methods(["POST"])
@transaction.atomic
def registrar_pagamento(request, id):
    """
    API: Registrar pagamento de um pedido
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)
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

        pagamento = PagamentoPedido.objects.create(
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


@csrf_exempt
@require_http_methods(["PATCH"])
def atualizar_status_pedido(request, id):
    """
    API: Atualizar o status do pedido com validação de fluxo
    """
    print(f"[DEBUG] Recebendo requisição PATCH para pedido {id}")

    try:
        pedido = get_object_or_404(Pedido, id=id)

        # Log do body da requisição
        print(f"[DEBUG] Request body: {request.body}")

        # Tentar ler o body da requisição
        try:
            data = json.loads(request.body)
            print(f"[DEBUG] JSON decodificado: {data}")
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON decode error: {e}")
            return JsonResponse({'success': False, 'error': f'JSON inválido: {str(e)}'}, status=400)

        novo_status = data.get('status')
        print(f"[DEBUG] Novo status solicitado: {novo_status}")

        # Verificar se o status foi enviado
        if not novo_status:
            return JsonResponse({'success': False, 'error': 'Status não informado'}, status=400)

        # Mapeamento de status permitidos
        STATUS_VALIDOS = ['pendente', 'completo', 'pronto', 'entregue']

        if novo_status not in STATUS_VALIDOS:
            return JsonResponse({
                'success': False,
                'error': f'Status inválido: {novo_status}. Status permitidos: {", ".join(STATUS_VALIDOS)}'
            }, status=400)

        status_atual = pedido.status
        print(f"[DEBUG] Status atual: {status_atual}")

        # Se o status for o mesmo, retorna erro
        if status_atual == novo_status:
            return JsonResponse({
                'success': False,
                'error': f'O pedido já está como {novo_status}'
            }, status=400)

        # Regras de transição de status
        transicoes_permitidas = {
            'pendente': ['completo'],
            'completo': ['pronto'],
            'pronto': ['entregue'],
            'entregue': []
        }

        # Verificar se a transição é permitida
        if novo_status not in transicoes_permitidas.get(status_atual, []):
            return JsonResponse({
                'success': False,
                'error': f'Transição inválida! Não é possível alterar de "{status_atual}" para "{novo_status}". Transições permitidas: {transicoes_permitidas.get(status_atual, [])}'
            }, status=400)

        # Regra especial: para entregar, precisa ter saldo zero
        if novo_status == 'entregue' and pedido.saldo > 0:
            return JsonResponse({
                'success': False,
                'error': f'Não é possível entregar o pedido pois há saldo pendente de {float(pedido.saldo):.2f} MT'
            }, status=400)

        # Atualizar o status
        pedido.status = novo_status
        pedido.save()

        print(f"[DEBUG] Status atualizado com sucesso para {novo_status}")

        return JsonResponse({
            'success': True,
            'message': f'Status do pedido #{pedido.id} atualizado para {novo_status}!',
            'status': novo_status,
            'status_label': novo_status.capitalize()
        })

    except Pedido.DoesNotExist:
        print(f"[ERROR] Pedido {id} não encontrado")
        return JsonResponse({'success': False, 'error': 'Pedido não encontrado'}, status=404)
    except Exception as e:
        print(f"[ERROR] Erro inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Erro interno: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def excluir_pedido(request, id):
    """
    API: Excluir pedido
    """
    try:
        pedido = get_object_or_404(Pedido, id=id)

        if pedido.status_pagamento == 'pago':
            return JsonResponse({'success': False, 'error': 'Não é possível excluir um pedido já pago'}, status=400)

        pedido.delete()

        return JsonResponse({
            'success': True,
            'message': 'Pedido excluído com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


import io
import os
import base64
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Sum, OuterRef, Subquery, Value, DecimalField, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta


def recibo_termico_view(request, pedido_id):
    """
    View para gerar imagem do recibo térmico
    """
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # Subquery: soma pagamentos por pedido
    pagos_subq = (
        PagamentoPedido.objects
        .filter(pedido=OuterRef("pk"))
        .values("pedido")
        .annotate(s=Sum("valor"))
        .values("s")[:1]
    )

    # Buscar todos os pedidos não pagos do mesmo cliente (inclui parcial)
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

    # Total em dívida (Decimal safe)
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

    # Valor pago neste pedido (soma dos pagamentos)
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

    # Desconto fidelidade aplicado
    desconto_aplicado = pedido.desconto or Decimal("0.00")

    # Pontos do pedido
    mov_pontos = MovimentacaoPontos.objects.filter(pedido=pedido, tipo="ganho").first()
    pontos_ganhos = mov_pontos.pontos if mov_pontos else 0

    # Pontos totais do cliente
    pontos_totais = pedido.cliente.pontos

    # Saldo
    saldo = pedido.saldo

    # Data de validade dos pontos (90 dias após a compra)
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


def recibo_termico_view(request, id):
    """
    View para gerar página HTML do recibo térmico
    """
    pedido = get_object_or_404(Pedido, id=id)

    # Subquery: soma pagamentos por pedido
    pagos_subq = (
        PagamentoPedido.objects
        .filter(pedido=OuterRef("pk"))
        .values("pedido")
        .annotate(s=Sum("valor"))
        .values("s")[:1]
    )

    # Buscar todos os pedidos não pagos do mesmo cliente
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

    # Total em dívida
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

    # Valor pago neste pedido
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

    # Desconto fidelidade aplicado
    desconto_aplicado = pedido.desconto or Decimal("0.00")
    saldo = pedido.saldo

    # Pontos do pedido
    from core.models import MovimentacaoPontos
    mov_pontos = MovimentacaoPontos.objects.filter(pedido=pedido, tipo="ganho").first()
    pontos_ganhos = mov_pontos.pontos if mov_pontos else 0

    # Pontos totais do cliente
    pontos_totais = pedido.cliente.pontos

    # Data de validade dos pontos (90 dias após a compra)
    from datetime import timedelta
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


def imprimir_recibo_imagem(request, id):
    """
    API: Gerar imagem do recibo térmico
    """
    pedido = get_object_or_404(Pedido, id=id)

    # Subquery: soma pagamentos por pedido
    pagos_subq = (
        PagamentoPedido.objects
        .filter(pedido=OuterRef("pk"))
        .values("pedido")
        .annotate(s=Sum("valor"))
        .values("s")[:1]
    )

    # Buscar todos os pedidos não pagos do mesmo cliente
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

    from core.models import MovimentacaoPontos
    mov_pontos = MovimentacaoPontos.objects.filter(pedido=pedido, tipo="ganho").first()
    pontos_ganhos = mov_pontos.pontos if mov_pontos else 0
    pontos_totaux = pedido.cliente.pontos
    from datetime import timedelta
    data_validade_pontos = pedido.criado_em + timedelta(days=90)

    # Renderizar o texto do recibo
    recibo_texto = render_to_string("pedidos/recibo_termico.txt", {
        "pedido": pedido,
        "pedidos_nao_pagos": pedidos_nao_pagos,
        "total_em_divida": total_em_divida,
        "valor_pago": valor_pago,
        "saldo": saldo,
        "desconto_aplicado": desconto_aplicado,
        "pontos_ganhos": pontos_ganhos,
        "pontos_totais": pontos_totaux,
        "data_validade_pontos": data_validade_pontos,
    })

    # Criar imagem
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        import base64
        import os
        from django.conf import settings

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
        # Se PIL não estiver instalado, retornar o HTML normal
        return render(request, 'pedidos/recibo_termico.html', {
            "pedido": pedido,
            "pedidos_nao_pagos": pedidos_nao_pagos,
            "total_em_divida": total_em_divida,
            "valor_pago": valor_pago,
            "saldo": saldo,
            "desconto_aplicado": desconto_aplicado,
            "pontos_ganhos": pontos_ganhos,
            "pontos_totais": pontos_totaux,
            "data_validade_pontos": data_validade_pontos,
        })


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from decimal import Decimal
import json
import requests
from core.models import Pedido, ItemPedido, Cliente, ItemServico, PagamentoPedido
from core.models import Lavandaria
from core.models import Funcionario
from core.models import MovimentacaoPontos
from django.db.models import Sum, Q
from django.db import transaction

# Configurações da API de SMS
SMS_API_URL = 'https://api.mozesms.com/v2/sms/bulk'
SMS_BEARER_TOKEN = 'Bearer 2374:zKNUpX-J4dao9-VEi60O-UeNqdN'
SMS_SENDER_ID = "POWERWASH"


def enviar_sms_mozesms(numero, mensagem, pedido=None, cliente=None):
    """
    Envia um SMS usando a API Mozesms
    """
    import re

    # Limpar o número (remover espaços, parênteses, etc.)
    numero_limpo = re.sub(r'\D', '', numero)

    # Se o número não tiver código do país, adicionar 258 (Moçambique)
    if len(numero_limpo) == 9:
        numero_limpo = '258' + numero_limpo
    elif len(numero_limpo) == 12 and numero_limpo.startswith('258'):
        pass
    else:
        numero_limpo = '258' + numero_limpo

    # Validar tamanho do número
    if len(numero_limpo) != 12:
        return False, f"Número inválido: {numero}"

    payload = {
        'sender_id': SMS_SENDER_ID,
        'messages': [
            {
                'phone': numero_limpo,
                'message': mensagem
            }
        ]
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
                # Verificar se a resposta indica sucesso
                if json_resposta.get('success') or json_resposta.get('status') == 'success':
                    print(f"SMS enviado com sucesso para {numero}")
                    return True, json_resposta
                else:
                    erro_msg = json_resposta.get('message', json_resposta.get('error', 'Erro desconhecido'))
                    print(f"Erro ao enviar SMS: {erro_msg}")
                    return False, erro_msg
            except Exception as e:
                print(f"Erro ao processar resposta JSON: {e}")
                return False, str(e)
        else:
            print(f"Erro na requisição: {response.status_code} - {response.text}")
            return False, f"HTTP {response.status_code}"

    except requests.RequestException as e:
        print(f"Erro ao enviar SMS: {e}")
        return False, str(e)



@csrf_exempt
@require_http_methods(["POST"])
def enviar_sms_pedido_pronto(request, pedido_id):
    """
    API: Enviar SMS notificando que o pedido está pronto
    """
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        cliente = pedido.cliente

        # Verificar se o pedido está pronto
        if pedido.status != 'pronto':
            return JsonResponse({
                'success': False,
                'error': f'O pedido não está com status "Pronto". Status atual: {pedido.get_status_display()}'
            }, status=400)

        # Verificar se o cliente tem telefone
        if not cliente.telefone:
            return JsonResponse({
                'success': False,
                'error': 'Cliente não possui número de telefone cadastrado'
            }, status=400)

        # Construir mensagem
        lavandaria = pedido.lavandaria

        mensagem = f"""🏷️ POWERWASH - Pedido Pronto!

Olá {cliente.nome},
Seu pedido #{pedido.id} está PRONTO para retirada!

📍 {lavandaria.endereco}
📞 Contato: {lavandaria.telefone}

⚠️ Você tem 30 dias para retirar.
Após este prazo, será aplicada taxa de armazenamento.

Obrigado pela preferência! 🙏"""

        # Enviar SMS
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



@csrf_exempt
@require_http_methods(["POST"])
def enviar_sms_cobranca(request, pedido_id):
    """
    API: Enviar SMS de cobrança para pedido com saldo pendente
    """
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        cliente = pedido.cliente
        saldo = pedido.saldo

        # Verificar se há saldo pendente
        if saldo <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Pedido não possui saldo pendente'
            }, status=400)

        # Verificar se o cliente tem telefone
        if not cliente.telefone:
            return JsonResponse({
                'success': False,
                'error': 'Cliente não possui número de telefone cadastrado'
            }, status=400)

        # Construir mensagem de cobrança
        lavandaria = pedido.lavandaria

        mensagem = f"""⚠️ POWERWASH - Pagamento Pendente!

Olá {cliente.nome},
Seu pedido #{pedido.id} tem saldo pendente de {saldo:.2f} MT.

💰 Total: {pedido.total_final:.2f} MT
💵 Pago: {(pedido.total_final - saldo):.2f} MT
💳 Saldo: {saldo:.2f} MT

📍 Efetue o pagamento na loja:
{lavandaria.endereco}
📞 {lavandaria.telefone}

Evite atrasos! Regularize seu pagamento.

Obrigado! 🙏"""

        # Enviar SMS
        sucesso, resposta = enviar_sms_mozesms(cliente.telefone, mensagem, pedido, cliente)

        if sucesso:
            return JsonResponse({
                'success': True,
                'message': f'SMS de cobrança enviado para {cliente.nome} ({cliente.telefone})'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Falha ao enviar SMS: {resposta}'
            }, status=500)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def enviar_sms_personalizado(request):
    """
    API: Enviar SMS personalizado para um ou múltiplos clientes
    """
    try:
        data = json.loads(request.body)
        cliente_ids = data.get('cliente_ids', [])
        mensagem = data.get('mensagem', '')
        pedido_id = data.get('pedido_id', None)

        if not mensagem:
            return JsonResponse({'success': False, 'error': 'Mensagem é obrigatória'}, status=400)

        if not cliente_ids and not pedido_id:
            return JsonResponse({'success': False, 'error': 'Selecione pelo menos um cliente ou pedido'}, status=400)

        # Se for enviado por pedido
        if pedido_id:
            pedido = get_object_or_404(Pedido, id=pedido_id)
            if pedido.cliente.telefone:
                cliente_ids = [pedido.cliente.id]
            else:
                return JsonResponse({'success': False, 'error': 'Cliente não tem telefone'}, status=400)

        # Buscar clientes
        clientes = Cliente.objects.filter(id__in=cliente_ids, telefone__isnull=False).exclude(telefone='')

        if not clientes.exists():
            return JsonResponse({'success': False, 'error': 'Nenhum cliente com telefone válido encontrado'},
                                status=400)

        resultados = []
        enviados = 0
        erros = 0

        for cliente in clientes:
            sucesso, resposta = enviar_sms_mozesms(cliente.telefone, mensagem)
            if sucesso:
                enviados += 1
                resultados.append({'cliente': cliente.nome, 'telefone': cliente.telefone, 'status': 'enviado'})
            else:
                erros += 1
                resultados.append(
                    {'cliente': cliente.nome, 'telefone': cliente.telefone, 'status': 'erro', 'erro': resposta})

        return JsonResponse({
            'success': True,
            'message': f'SMS enviados: {enviados} sucesso, {erros} falhas',
            'resultados': resultados
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def enviar_sms_teste(request):
    """
    API: Enviar SMS de teste para verificar configuração
    """
    try:
        data = json.loads(request.body)
        telefone_teste = data.get('telefone', '')

        if not telefone_teste:
            return JsonResponse({'success': False, 'error': 'Telefone é obrigatório'}, status=400)

        mensagem_teste = """🧪 POWERWASH - Teste de SMS

Esta é uma mensagem de teste do sistema PowerWash.

Se você recebeu esta mensagem, o sistema de SMS está funcionando corretamente!

Data e hora do teste: {} 

Obrigado! 🙏""".format(timezone.now().strftime('%d/%m/%Y %H:%M:%S'))

        sucesso, resposta = enviar_sms_mozesms(telefone_teste, mensagem_teste)

        if sucesso:
            return JsonResponse({
                'success': True,
                'message': f'SMS de teste enviado com sucesso para {telefone_teste}'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Falha ao enviar SMS de teste: {resposta}'
            }, status=500)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)