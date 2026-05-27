from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json
from core.models import Cliente, MovimentacaoPontos, Pedido
from django.db.models import Sum, Count, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Count, Q, Value, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from decimal import Decimal
import json
from core.models import Cliente, MovimentacaoPontos, Pedido


def ver_cliente(request):
    return render(request, 'cliente/cliente.html')


@csrf_exempt
@require_http_methods(["GET"])
def listar_clientes(request):
    """
    API: Listar clientes (VERSÃO OTIMIZADA PARA ÍNDICES)
    """
    try:
        search = request.GET.get('search', '')
        points_filter = request.GET.get('points_filter', 'all')
        sort_by = request.GET.get('sort_by', 'name')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))

        # Query principal com SELECT_RELATED e ANNOTATE
        clientes = Cliente.objects.all()

        # 🔥 USANDO ÍNDICE: filtro de busca (nome e telefone têm índices)
        if search:
            clientes = clientes.filter(
                Q(nome__icontains=search) |
                Q(telefone__icontains=search)
            )

        # 🔥 USANDO ÍNDICE: filtro de pontos
        if points_filter == 'high':
            clientes = clientes.filter(pontos__gt=5000)
        elif points_filter == 'medium':
            clientes = clientes.filter(pontos__gte=1000, pontos__lte=5000)
        elif points_filter == 'low':
            clientes = clientes.filter(pontos__lt=1000)

        # Anotar totais (uma única query adicional)
        clientes = clientes.annotate(
            total_pedidos_count=Count('pedidos'),
            total_gasto_sum=Coalesce(
                Sum('pedidos__total') - Sum('pedidos__desconto') - Sum('pedidos__desconto_cabides'),
                Value(Decimal('0.00'), output_field=DecimalField())
            ),
            tem_pedido_recente=Count('pedidos',
                                     filter=Q(pedidos__criado_em__gte=timezone.now() - timezone.timedelta(days=30)))
        )

        # 🔥 USANDO ÍNDICE: ordenação
        if sort_by == 'name':
            clientes = clientes.order_by('nome')  # índice em 'nome'
        elif sort_by == 'points':
            clientes = clientes.order_by('-pontos')  # índice em 'pontos'
        elif sort_by == 'total_gasto':
            clientes = clientes.order_by('-total_gasto_sum')
        elif sort_by == 'recent':
            clientes = clientes.order_by('-criado_em')  # índice em 'criado_em'
        else:
            clientes = clientes.order_by('-id')

        # Paginação (count é rápido com índices)
        total = clientes.count()
        start = (page - 1) * per_page
        end = start + per_page
        clientes_paginados = clientes[start:end]

        # Montar resposta (sem loops pesados)
        clientes_data = []
        for cliente in clientes_paginados:
            clientes_data.append({
                'id': cliente.id,
                'nome': cliente.nome,
                'telefone': cliente.telefone or '',
                'endereco': cliente.endereco or '',
                'pontos': cliente.pontos,
                'total_gasto_acumulado': float(cliente.total_gasto_acumulado),
                'total_gasto': float(cliente.total_gasto_sum or 0),
                'total_pedidos': cliente.total_pedidos_count or 0,
                'status': 'active' if cliente.tem_pedido_recente > 0 else 'inactive',
                'criado_em': cliente.criado_em.strftime('%Y-%m-%d') if hasattr(cliente,
                                                                               'criado_em') else timezone.now().strftime(
                    '%Y-%m-%d')
            })

        return JsonResponse({
            'success': True,
            'clientes': clientes_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
def estatisticas_clientes(request):
    """
    API: Estatísticas rápidas (com cache opcional)
    """
    try:
        # Todas em uma única query agregada
        stats = Cliente.objects.aggregate(
            total_clientes=Count('id'),
            total_pontos=Coalesce(Sum('pontos'), 0),
            total_gasto_acumulado=Coalesce(Sum('total_gasto_acumulado'), Decimal('0.00'))
        )

        # Clientes ativos (subquery eficiente)
        ultimos_30_dias = timezone.now() - timezone.timedelta(days=30)
        clientes_ativos = Cliente.objects.filter(
            pedidos__criado_em__gte=ultimos_30_dias
        ).distinct().count()

        # Novos clientes este mês
        inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        novos_clientes_mes = Cliente.objects.filter(criado_em__gte=inicio_mes).count()

        total_clientes = stats['total_clientes'] or 0

        return JsonResponse({
            'success': True,
            'estatisticas': {
                'total_clientes': total_clientes,
                'clientes_ativos': clientes_ativos,
                'percentual_ativos': round((clientes_ativos / total_clientes * 100), 1) if total_clientes > 0 else 0,
                'total_pontos': stats['total_pontos'] or 0,
                'total_gasto': float(stats['total_gasto_acumulado'] or 0),
                'novos_clientes_mes': novos_clientes_mes
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)




@csrf_exempt
@require_http_methods(["POST"])
def criar_cliente(request):
    """
    API: Criar novo cliente
    """
    try:
        data = json.loads(request.body)
        nome = data.get('nome')
        telefone = data.get('telefone')
        endereco = data.get('endereco', '')

        if not nome:
            return JsonResponse({'success': False, 'error': 'Nome é obrigatório'}, status=400)

        cliente = Cliente.objects.create(
            nome=nome,
            telefone=telefone,
            endereco=endereco,
            pontos=0,
            total_gasto_acumulado=Decimal('0.00')
        )

        return JsonResponse({
            'success': True,
            'cliente': {
                'id': cliente.id,
                'nome': cliente.nome,
                'telefone': cliente.telefone,
                'endereco': cliente.endereco,
                'pontos': cliente.pontos,
                'pontos_validos': 0,
                'total_gasto_acumulado': float(cliente.total_gasto_acumulado),
                'total_gasto': 0,
                'total_pedidos': 0,
                'status': 'inactive',
                'criado_em': timezone.now().strftime('%Y-%m-%d')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
def editar_cliente(request, id):
    """
    API: Editar cliente existente
    """
    try:
        cliente = get_object_or_404(Cliente, id=id)
        data = json.loads(request.body)

        if 'nome' in data:
            cliente.nome = data['nome']
        if 'telefone' in data:
            cliente.telefone = data['telefone']
        if 'endereco' in data:
            cliente.endereco = data['endereco']

        cliente.save()

        # 🔥 OTIMIZAÇÃO: Usar aggregate para calcular totais
        totais = Pedido.objects.filter(cliente=cliente).aggregate(
            total_gasto=Coalesce(Sum('total_final'), Decimal('0.00')),
            total_pedidos=Count('id')
        )

        return JsonResponse({
            'success': True,
            'cliente': {
                'id': cliente.id,
                'nome': cliente.nome,
                'telefone': cliente.telefone,
                'endereco': cliente.endereco,
                'pontos': cliente.pontos,
                'pontos_validos': cliente.pontos_validos(),
                'total_gasto_acumulado': float(cliente.total_gasto_acumulado),
                'total_gasto': float(totais['total_gasto']),
                'total_pedidos': totais['total_pedidos'],
                'criado_em': cliente.criado_em.strftime('%Y-%m-%d') if hasattr(cliente,
                                                                               'criado_em') else timezone.now().strftime(
                    '%Y-%m-%d')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def ajustar_pontos_cliente(request, id):
    """
    API: Ajustar pontos do cliente
    """
    try:
        cliente = get_object_or_404(Cliente, id=id)
        data = json.loads(request.body)

        pontos = int(data.get('pontos', 0))
        motivo = data.get('motivo', 'ajuste')

        if pontos == 0:
            return JsonResponse({'success': False, 'error': 'Quantidade de pontos inválida'}, status=400)

        cliente.pontos += pontos
        if cliente.pontos < 0:
            cliente.pontos = 0
        cliente.save()

        # Registrar movimentação de pontos
        MovimentacaoPontos.objects.create(
            cliente=cliente,
            tipo='ajuste',
            pontos=pontos,
            criado_por=request.user.funcionario if hasattr(request.user, 'funcionario') else None
        )

        return JsonResponse({
            'success': True,
            'message': f'Pontos {pontos > 0 and "adicionados" or "removidos"} com sucesso',
            'pontos_atuais': cliente.pontos,
            'pontos_alterados': pontos
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def excluir_cliente(request, id):
    """
    API: Excluir cliente
    """
    try:
        cliente = get_object_or_404(Cliente, id=id)
        nome = cliente.nome
        cliente.delete()

        return JsonResponse({
            'success': True,
            'message': f'Cliente "{nome}" excluído com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def excluir_multiplos_clientes(request):
    """
    API: Excluir múltiplos clientes
    """
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        if not ids:
            return JsonResponse({'success': False, 'error': 'Nenhum cliente selecionado'}, status=400)

        clientes = Cliente.objects.filter(id__in=ids)
        quantidade = clientes.count()
        clientes.delete()

        return JsonResponse({
            'success': True,
            'message': f'{quantidade} cliente(s) excluído(s) com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)





@csrf_exempt
@require_http_methods(["GET"])
def historico_pontos_cliente(request, id):
    """
    API: Obter histórico de pontos do cliente
    """
    try:
        cliente = get_object_or_404(Cliente, id=id)
        movimentacoes = cliente.movimentacoes_pontos.all().order_by('-criado_em')[:20]

        historico = []
        for mov in movimentacoes:
            historico.append({
                'id': mov.id,
                'tipo': mov.get_tipo_display(),
                'pontos': mov.pontos,
                'criado_em': mov.criado_em.strftime('%d/%m/%Y %H:%M'),
                'pedido_id': mov.pedido.id if mov.pedido else None
            })

        return JsonResponse({
            'success': True,
            'historico': historico
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)