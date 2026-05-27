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


def ver_cliente(request):
    """
    View para página de gerenciamento de clientes
    """
    return render(request, 'cliente/cliente.html')


@csrf_exempt
@require_http_methods(["GET"])
def listar_clientes(request):
    """
    API: Listar todos os clientes (VERSÃO OTIMIZADA)
    """
    try:
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))

        # Query base
        clientes = Cliente.objects.all()

        # Aplicar filtro de busca
        if search:
            clientes = clientes.filter(
                Q(nome__icontains=search) |
                Q(telefone__icontains=search)
            )

        # 🔥 OTIMIZAÇÃO: Anotar totais em uma única query
        clientes = clientes.annotate(
            total_pedidos_count=Count('pedidos'),
            total_gasto_sum=Coalesce(Sum('pedidos__total_final'), Decimal('0.00')),
            tem_pedido_recente=Count('pedidos',
                                     filter=Q(pedidos__criado_em__gte=timezone.now() - timezone.timedelta(days=30)))
        )

        # Ordenar
        clientes = clientes.order_by('-id')

        # Paginação
        paginator = Paginator(clientes, per_page)
        page_obj = paginator.get_page(page)

        clientes_data = []
        for cliente in page_obj:
            # Usar valores anotados (evita queries adicionais)
            total_gasto = cliente.total_gasto_sum or Decimal('0.00')
            total_pedidos = cliente.total_pedidos_count or 0
            tem_pedido_recente = cliente.tem_pedido_recente > 0

            clientes_data.append({
                'id': cliente.id,
                'nome': cliente.nome,
                'telefone': cliente.telefone or '',
                'endereco': cliente.endereco or '',
                'pontos': cliente.pontos,
                'pontos_validos': cliente.pontos_validos(),
                'total_gasto_acumulado': float(cliente.total_gasto_acumulado),
                'total_gasto': float(total_gasto),
                'total_pedidos': total_pedidos,
                'status': 'active' if tem_pedido_recente else 'inactive',
                'criado_em': cliente.criado_em.strftime('%Y-%m-%d') if hasattr(cliente,
                                                                               'criado_em') else timezone.now().strftime(
                    '%Y-%m-%d')
            })

        return JsonResponse({
            'success': True,
            'clientes': clientes_data,
            'total': paginator.count,
            'page': page,
            'per_page': per_page,
            'total_pages': paginator.num_pages
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
def estatisticas_clientes(request):
    """
    API: Obter estatísticas dos clientes
    """
    try:
        total_clientes = Cliente.objects.count()

        # Clientes ativos (com pedido nos últimos 30 dias)
        ultimos_30_dias = timezone.now() - timezone.timedelta(days=30)
        clientes_ativos = Cliente.objects.filter(
            pedidos__criado_em__gte=ultimos_30_dias
        ).distinct().count()

        # Total de pontos
        total_pontos = Cliente.objects.aggregate(total=Coalesce(Sum('pontos'), 0))['total']

        # Total gasto acumulado
        total_gasto_acumulado = Cliente.objects.aggregate(
            total=Coalesce(Sum('total_gasto_acumulado'), Decimal('0.00'))
        )['total']

        # Novos clientes este mês
        inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        novos_clientes_mes = Cliente.objects.filter(
            criado_em__gte=inicio_mes
        ).count()

        return JsonResponse({
            'success': True,
            'estatisticas': {
                'total_clientes': total_clientes,
                'clientes_ativos': clientes_ativos,
                'percentual_ativos': round((clientes_ativos / total_clientes * 100), 1) if total_clientes > 0 else 0,
                'total_pontos': total_pontos,
                'total_gasto': float(total_gasto_acumulado),
                'novos_clientes_mes': novos_clientes_mes
            }
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