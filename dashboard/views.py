from django.shortcuts import render
from django.db.models import Sum, Count, Q, Avg, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Pedido, Cliente, ItemServico, Funcionario, PagamentoPedido, MovimentacaoPontos


def dashboard(request):
    # Usuário e lavandaria
    usuario_logado = request.user
    lavandaria_usuario = None
    nome_funcionario = ""
    nome_lavandaria = "PowerWash"

    if hasattr(usuario_logado, 'funcionario'):
        lavandaria_usuario = usuario_logado.funcionario.lavandaria
        nome_funcionario = usuario_logado.get_full_name() or usuario_logado.username
        if lavandaria_usuario:
            nome_lavandaria = lavandaria_usuario.nome

    hoje = timezone.now().date()
    inicio_hoje = timezone.make_aware(timezone.datetime.combine(hoje, timezone.datetime.min.time()))
    fim_hoje = timezone.make_aware(timezone.datetime.combine(hoje, timezone.datetime.max.time()))

    # Filtros por lavandaria
    if lavandaria_usuario:
        pedidos_query = Pedido.objects.filter(lavandaria=lavandaria_usuario)
        clientes_query = Cliente.objects.filter(pedidos__lavandaria=lavandaria_usuario).distinct()
    else:
        pedidos_query = Pedido.objects.all()
        clientes_query = Cliente.objects.all()

    # ========== 1. MÉTRICAS PRINCIPAIS ==========

    # Pedidos hoje
    pedidos_hoje = pedidos_query.filter(criado_em__range=[inicio_hoje, fim_hoje])
    total_pedidos_hoje = pedidos_hoje.count()
    receita_hoje = pedidos_hoje.aggregate(total=Sum('total_pago'))['total'] or Decimal('0.00')

    # Ticket médio (usando total_pago pois total_final é property)
    ticket_medio = pedidos_query.aggregate(
        media=Avg('total_pago')
    )['media'] or Decimal('0.00')

    # Pedidos por status
    pedidos_pendentes = pedidos_query.filter(status='pendente').count()
    pedidos_completos = pedidos_query.filter(status='completo').count()
    pedidos_prontos = pedidos_query.filter(status='pronto').count()
    pedidos_entregues = pedidos_query.filter(status='entregue').count()

    # Taxa de conclusão
    total_pedidos = pedidos_query.count()
    if total_pedidos > 0:
        taxa_conclusao = ((pedidos_entregues + pedidos_prontos) / total_pedidos) * 100
    else:
        taxa_conclusao = 0

    # Pedidos em atraso (pendentes há mais de 3 dias)
    limite_atraso = timezone.now() - timedelta(days=3)
    pedidos_atraso = pedidos_query.filter(
        status='pendente',
        criado_em__lte=limite_atraso
    ).count()

    # Clientes ativos
    ultimos_30_dias = hoje - timedelta(days=30)
    clientes_ativos = clientes_query.filter(
        pedidos__criado_em__gte=timezone.make_aware(
            timezone.datetime.combine(ultimos_30_dias, timezone.datetime.min.time()))
    ).distinct().count()

    # Clientes fiéis (com pontos > 1000)
    clientes_fieis = clientes_query.filter(pontos__gt=1000).count()

    # Total de pontos ativos
    total_pontos = clientes_query.aggregate(total=Sum('pontos'))['total'] or 0

    # ========== 2. MÉTRICAS FINANCEIRAS AVANÇADAS ==========

    # Saldo pendente total (calculado em Python, não no banco)
    pedidos_nao_pagos = pedidos_query.exclude(status_pagamento='pago')
    saldo_pendente_total = Decimal('0.00')
    for pedido in pedidos_nao_pagos:
        saldo_pendente_total += pedido.saldo

    # Descontos totais (campos diretos do banco)
    total_desconto_fidelidade = pedidos_query.aggregate(total=Sum('desconto'))['total'] or Decimal('0.00')
    total_desconto_cabides = pedidos_query.aggregate(total=Sum('desconto_cabides'))['total'] or Decimal('0.00')

    # Total de cabides trazidos
    total_cabides = pedidos_query.aggregate(total=Sum('cabides_trazidos'))['total'] or 0

    # Métodos de pagamento
    metodos_pagamento = PagamentoPedido.objects.filter(
        pedido__in=pedidos_query
    ).values('metodo_pagamento').annotate(
        total=Sum('valor'),
        quantidade=Count('id')
    ).order_by('-total')[:5]

    # ========== 3. GRÁFICOS ==========

    # Receita últimos 7 dias
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    dados_semana = []
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        inicio_dia = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.min.time()))
        fim_dia = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.max.time()))

        receita_dia = pedidos_query.filter(
            criado_em__range=[inicio_dia, fim_dia]
        ).aggregate(total=Sum('total_pago'))['total'] or Decimal('0.00')

        pedidos_dia = pedidos_query.filter(
            criado_em__range=[inicio_dia, fim_dia]
        ).count()

        dias_pt = {
            'Monday': 'Segunda',
            'Tuesday': 'Terça',
            'Wednesday': 'Quarta',
            'Thursday': 'Quinta',
            'Friday': 'Sexta',
            'Saturday': 'Sábado',
            'Sunday': 'Domingo'
        }

        dados_semana.append({
            'dia': dia.strftime('%A'),
            'dia_curto': dias_pt.get(dia.strftime('%A'), dia.strftime('%a'))[:3],
            'receita': float(receita_dia),
            'pedidos': pedidos_dia
        })

    # Top 5 clientes (usando valores calculados em Python)
    # Top 5 clientes (otimizado)
    todos_clientes = []

    if lavandaria_usuario:
        # Filtra pedidos apenas da lavandaria atual
        for cliente in clientes_query.all():
            pedidos_cliente = cliente.pedidos.filter(lavandaria=lavandaria_usuario)
            total_gasto = sum(pedido.total_final for pedido in pedidos_cliente)
            total_pedidos_count = pedidos_cliente.count()

            if total_gasto > 0:
                todos_clientes.append({
                    'cliente__nome': cliente.nome,
                    'cliente__id': cliente.id,
                    'total_gasto': total_gasto,
                    'total_pedidos': total_pedidos_count
                })
    else:
        # Sem filtro de lavandaria - todos os pedidos
        for cliente in clientes_query.all():
            pedidos_cliente = cliente.pedidos.all()
            total_gasto = sum(pedido.total_final for pedido in pedidos_cliente)
            total_pedidos_count = pedidos_cliente.count()

            if total_gasto > 0:
                todos_clientes.append({
                    'cliente__nome': cliente.nome,
                    'cliente__id': cliente.id,
                    'total_gasto': total_gasto,
                    'total_pedidos': total_pedidos_count
                })

    top_clientes = sorted(todos_clientes, key=lambda x: x['total_gasto'], reverse=True)[:5]

    top_clientes = sorted(todos_clientes, key=lambda x: x['total_gasto'], reverse=True)[:5]

    # Top produtos mais vendidos
    top_produtos = ItemServico.objects.filter(
        itens__pedido__in=pedidos_query
    ).annotate(
        total_vendido=Coalesce(Sum('itens__quantidade'), Value(0)),
        receita_total=Coalesce(Sum('itens__preco_total'), Value(0, output_field=DecimalField()))
    ).filter(total_vendido__gt=0).order_by('-total_vendido')[:5]

    # Performance por funcionário
    performance_funcionarios = pedidos_query.values(
        'funcionario__user__username'
    ).annotate(
        total_pedidos=Count('id'),
        receita_total=Sum('total_pago')
    ).order_by('-total_pedidos')[:5]

    # Status distribution
    status_data = []
    status_choices = dict(Pedido.STATUS_CHOICES)
    for status_code, status_name in status_choices.items():
        count = pedidos_query.filter(status=status_code).count()
        if count > 0:
            status_data.append({
                'status': status_name,
                'quantidade': count,
                'cor': _get_status_color(status_code)
            })

    # ========== 4. ALERTAS E NOTIFICAÇÕES ==========

    alertas = []

    # Pontos prestes a expirar (próximos 30 dias)
    data_limite = timezone.now() - timedelta(days=60)
    pontos_expirando = clientes_query.filter(
        movimentacoes_pontos__tipo='ganho',
        movimentacoes_pontos__criado_em__lte=data_limite
    ).distinct().count()

    if pontos_expirando > 0:
        alertas.append({
            'tipo': 'warning',
            'mensagem': f'{pontos_expirando} clientes têm pontos a expirar nos próximos 30 dias'
        })

    if pedidos_atraso > 0:
        alertas.append({
            'tipo': 'danger',
            'mensagem': f'{pedidos_atraso} pedidos estão em atraso há mais de 3 dias'
        })

    # ========== 5. PEDIDOS RECENTES ==========
    pedidos_recentes = pedidos_query.select_related('cliente').order_by('-criado_em')[:10]
    pedidos_data = []
    for pedido in pedidos_recentes:
        total_itens = pedido.itens.aggregate(total=Sum('quantidade'))['total'] or 0
        pedidos_data.append({
            'id': f'#{pedido.id:06d}',
            'cliente': pedido.cliente.nome,
            'itens': f'{total_itens} {"item" if total_itens == 1 else "itens"}',
            'total': f'{float(pedido.total_final):,.0f} MT'.replace(',', '.'),
            'status': pedido.status,
            'status_label': dict(Pedido.STATUS_CHOICES).get(pedido.status, pedido.status),
            'status_color': _get_status_color(pedido.status),
            'pagamento': pedido.status_pagamento,
            'pagamento_label': dict(Pedido.STATUS_PAGAMENTO_CHOICES).get(pedido.status_pagamento,
                                                                         pedido.status_pagamento),
            'pagamento_color': _get_pagamento_color(pedido.status_pagamento),
        })

    context = {
        # Métricas principais
        'stats': {
            'pedidos_hoje': total_pedidos_hoje,
            'receita_hoje': f'{float(receita_hoje):,.0f} MT'.replace(',', '.'),
            'ticket_medio': f'{float(ticket_medio):,.0f} MT'.replace(',', '.'),
            'clientes_ativos': clientes_ativos,
            'clientes_fieis': clientes_fieis,
            'pedidos_atraso': pedidos_atraso,
            'taxa_conclusao': round(taxa_conclusao, 1),
            'total_pontos': total_pontos,
            'saldo_pendente': f'{float(saldo_pendente_total):,.0f} MT'.replace(',', '.'),
            'total_desconto_fidelidade': f'{float(total_desconto_fidelidade):,.0f} MT'.replace(',', '.'),
            'total_desconto_cabides': f'{float(total_desconto_cabides):,.0f} MT'.replace(',', '.'),
            'total_cabides': total_cabides,
        },

        # Gráficos
        'dados_semana': dados_semana,
        'status_data': status_data,
        'top_clientes': top_clientes,
        'top_produtos': top_produtos,
        'performance_funcionarios': performance_funcionarios,
        'metodos_pagamento': list(metodos_pagamento),

        # Alertas
        'alertas': alertas,

        # Outros
        'pedidos_recentes': pedidos_data,
        'lavandaria_nome': nome_lavandaria,
        'funcionario_nome': nome_funcionario,
        'usuario_logado': usuario_logado,
    }

    return render(request, "dashboard/dashboard.html", context)


def _get_status_color(status):
    cores = {
        'pendente': 'yellow',
        'completo': 'blue',
        'pronto': 'green',
        'entregue': 'purple',
    }
    return cores.get(status, 'gray')


def _get_pagamento_color(status_pagamento):
    cores = {
        'nao_pago': 'red',
        'parcial': 'yellow',
        'pago': 'green',
    }
    return cores.get(status_pagamento, 'gray')