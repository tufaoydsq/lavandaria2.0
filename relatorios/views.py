from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import TruncDay, TruncMonth
from core.models import Pedido, PagamentoPedido
from core.models import Cliente
from core.models import ItemServico


def ver_relatorios(request):
    """
    View para página de relatórios
    """
    return render(request, 'relatorios/relatorios.html')


@csrf_exempt
@require_http_methods(["GET"])
def dados_relatorios(request):
    """
    API: Obter dados para os relatórios
    """
    try:
        periodo = request.GET.get('periodo', 'mes')
        lavandaria_id = request.GET.get('lavandaria', 'all')
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')

        # Definir período
        agora = timezone.now()
        hoje = agora.date()

        if periodo == 'hoje':
            data_inicio = hoje
            data_fim = hoje
            data_inicio_anterior = hoje - timedelta(days=1)
            data_fim_anterior = hoje - timedelta(days=1)
        elif periodo == 'ontem':
            data_inicio = hoje - timedelta(days=1)
            data_fim = hoje - timedelta(days=1)
            data_inicio_anterior = hoje - timedelta(days=2)
            data_fim_anterior = hoje - timedelta(days=2)
        elif periodo == 'semana':
            data_inicio = hoje - timedelta(days=7)
            data_fim = hoje
            data_inicio_anterior = hoje - timedelta(days=14)
            data_fim_anterior = hoje - timedelta(days=8)
        elif periodo == 'mes':
            data_inicio = hoje.replace(day=1)
            data_fim = hoje
            data_inicio_anterior = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
            data_fim_anterior = hoje.replace(day=1) - timedelta(days=1)
        elif periodo == 'mes_passado':
            primeiro_dia_mes_passado = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
            ultimo_dia_mes_passado = hoje.replace(day=1) - timedelta(days=1)
            data_inicio = primeiro_dia_mes_passado
            data_fim = ultimo_dia_mes_passado
            data_inicio_anterior = primeiro_dia_mes_passado - timedelta(days=30)
            data_fim_anterior = ultimo_dia_mes_passado - timedelta(days=30)
        elif periodo == 'trimestre':
            data_inicio = hoje - timedelta(days=90)
            data_fim = hoje
            data_inicio_anterior = hoje - timedelta(days=180)
            data_fim_anterior = hoje - timedelta(days=91)
        elif periodo == 'ano':
            data_inicio = hoje.replace(month=1, day=1)
            data_fim = hoje
            data_inicio_anterior = hoje.replace(year=hoje.year - 1, month=1, day=1)
            data_fim_anterior = hoje.replace(year=hoje.year - 1, month=12, day=31)
        elif periodo == 'personalizado' and data_inicio_str and data_fim_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            dias_periodo = (data_fim - data_inicio).days
            data_inicio_anterior = data_inicio - timedelta(days=dias_periodo)
            data_fim_anterior = data_inicio - timedelta(days=1)
        else:
            data_inicio = hoje.replace(day=1)
            data_fim = hoje
            data_inicio_anterior = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
            data_fim_anterior = hoje.replace(day=1) - timedelta(days=1)

        # Converter para datetime
        inicio_periodo = timezone.make_aware(datetime.combine(data_inicio, datetime.min.time()))
        fim_periodo = timezone.make_aware(datetime.combine(data_fim, datetime.max.time()))
        inicio_anterior = timezone.make_aware(datetime.combine(data_inicio_anterior, datetime.min.time()))
        fim_anterior = timezone.make_aware(datetime.combine(data_fim_anterior, datetime.max.time()))

        # Filtrar pedidos
        pedidos_query = Pedido.objects.all()
        if lavandaria_id != 'all':
            pedidos_query = pedidos_query.filter(lavandaria_id=lavandaria_id)

        # Pedidos do período atual
        pedidos_periodo = pedidos_query.filter(criado_em__range=[inicio_periodo, fim_periodo])
        pedidos_anterior = pedidos_query.filter(criado_em__range=[inicio_anterior, fim_anterior])

        # ========== RESUMO ==========
        total_pedidos = pedidos_periodo.count()
        receita_total = pedidos_periodo.aggregate(total=Sum('total_pago'))['total'] or Decimal('0.00')
        ticket_medio = float(receita_total / total_pedidos) if total_pedidos > 0 else 0
        clientes_atendidos = pedidos_periodo.values('cliente').distinct().count()

        total_pedidos_anterior = pedidos_anterior.count()
        receita_anterior = pedidos_anterior.aggregate(total=Sum('total_pago'))['total'] or Decimal('0.00')

        variacao_pedidos = ((
                                        total_pedidos - total_pedidos_anterior) / total_pedidos_anterior * 100) if total_pedidos_anterior > 0 else 0
        variacao_receita = ((receita_total - receita_anterior) / receita_anterior * 100) if receita_anterior > 0 else 0

        # Novos clientes no período
        novos_clientes = Cliente.objects.filter(
            pedidos__criado_em__range=[inicio_periodo, fim_periodo]
        ).exclude(
            pedidos__criado_em__lt=inicio_periodo
        ).distinct().count()

        # ========== EVOLUÇÃO (últimos 30 dias) ==========
        evolucao = []
        for i in range(30):
            dia = data_fim - timedelta(days=29 - i)
            inicio_dia = timezone.make_aware(datetime.combine(dia, datetime.min.time()))
            fim_dia = timezone.make_aware(datetime.combine(dia, datetime.max.time()))
            pedidos_dia = pedidos_query.filter(criado_em__range=[inicio_dia, fim_dia])
            evolucao.append({
                'periodo': dia.strftime('%d/%m'),
                'pedidos': pedidos_dia.count(),
                'receita': float(pedidos_dia.aggregate(total=Sum('total_pago'))['total'] or 0)
            })

        # ========== DISTRIBUIÇÃO DE STATUS ==========
        status_distribuicao = []
        status_map = {
            'pendente': 'Pendente',
            'completo': 'Completo',
            'pronto': 'Pronto',
            'entregue': 'Entregue'
        }
        for status, label in status_map.items():
            count = pedidos_periodo.filter(status=status).count()
            if count > 0:
                status_distribuicao.append({'status': label, 'quantidade': count})

        # ========== MÉTODOS DE PAGAMENTO ==========
        pagamentos = PagamentoPedido.objects.filter(pedido__in=pedidos_periodo)
        metodos_pagamento = {}
        metodo_nomes = {
            'numerario': 'Numerário',
            'pos': 'POS',
            'mpesa': 'M-Pesa',
            'emola': 'e-Mola',
            'conta_movel': 'Conta Móvel',
            'transferencia': 'Transferência'
        }
        for pag in pagamentos:
            metodo = metodo_nomes.get(pag.metodo_pagamento, pag.metodo_pagamento)
            metodos_pagamento[metodo] = metodos_pagamento.get(metodo, 0) + float(pag.valor)

        pagamentos_data = [{'metodo': k, 'valor': v} for k, v in metodos_pagamento.items()]

        # ========== TOP PRODUTOS ==========
        top_produtos = ItemServico.objects.filter(
            itens__pedido__in=pedidos_periodo,
            itens__quantidade__gt=0
        ).annotate(
            total_vendido=Sum('itens__quantidade'),
            receita_total=Sum('itens__preco_total')
        ).filter(total_vendido__gt=0).order_by('-total_vendido')[:5]

        top_produtos_data = []
        for p in top_produtos:
            top_produtos_data.append({
                'nome': p.nome,
                'quantidade': p.total_vendido or 0,
                'receita': float(p.receita_total or 0)
            })

        # ========== HORÁRIOS DE MAIOR MOVIMENTO ==========
        horarios = {}
        for pedido in pedidos_periodo:
            hora = pedido.criado_em.hour
            horarios[hora] = horarios.get(hora, 0) + 1

        horarios_data = [{'hora': f'{h:02d}:00', 'pedidos': v} for h, v in sorted(horarios.items())]

        # ========== DIAS DA SEMANA ==========
        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        dias_data = []
        for dia in dias_semana:
            dias_data.append({'dia': dia, 'pedidos': 0, 'receita': 0})

        for pedido in pedidos_periodo:
            dia_semana = dias_semana[pedido.criado_em.weekday()]
            for d in dias_data:
                if d['dia'] == dia_semana:
                    d['pedidos'] += 1
                    d['receita'] += float(pedido.total_final)
                    break

        # ========== LISTA DE PEDIDOS ==========
        pedidos_lista = []
        for pedido in pedidos_periodo.select_related('cliente').order_by('-criado_em')[:100]:
            total_itens = pedido.itens.aggregate(total=Sum('quantidade'))['total'] or 0
            pedidos_lista.append({
                'id': pedido.id,
                'id_formatado': f'#{pedido.id:06d}',
                'cliente': pedido.cliente.nome,
                'data': pedido.criado_em.strftime('%d/%m/%Y %H:%M'),
                'itens': total_itens,
                'total': float(pedido.total_final),
                'status': pedido.status,
                'status_label': dict(Pedido.STATUS_CHOICES).get(pedido.status, pedido.status),
                'pagamento': pedido.status_pagamento,
                'pagamento_label': dict(Pedido.STATUS_PAGAMENTO_CHOICES).get(pedido.status_pagamento,
                                                                             pedido.status_pagamento)
            })

        return JsonResponse({
            'success': True,
            'resumo': {
                'total_pedidos': total_pedidos,
                'receita_total': float(receita_total),
                'ticket_medio': ticket_medio,
                'total_clientes': clientes_atendidos,
                'variacao_pedidos': round(variacao_pedidos, 1),
                'variacao_receita': round(variacao_receita, 1),
                'novos_clientes': novos_clientes
            },
            'evolucao': evolucao,
            'status_distribuicao': status_distribuicao,
            'pagamentos': pagamentos_data,
            'top_produtos': top_produtos_data,
            'horarios': horarios_data,
            'dias_semana': dias_data,
            'pedidos': pedidos_lista
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)