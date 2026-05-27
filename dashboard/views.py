from django.shortcuts import render
from django.db.models import Sum, Count, Q, Avg, F, Value, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Pedido, Cliente, ItemServico, Funcionario, PagamentoPedido, MovimentacaoPontos


def dashboard(request):
    # ========== 1. USUÁRIO E LAVANDARIA ==========
    usuario_logado = request.user
    lavandaria_usuario = None
    nome_funcionario = ""
    nome_lavandaria = "PowerWash"

    # Verificar se o usuário é funcionário e tem lavandaria associada
    if hasattr(usuario_logado, 'funcionario'):
        funcionario = usuario_logado.funcionario
        lavandaria_usuario = funcionario.lavandaria
        nome_funcionario = usuario_logado.get_full_name() or usuario_logado.username
        if lavandaria_usuario:
            nome_lavandaria = lavandaria_usuario.nome

    hoje = timezone.now().date()
    inicio_hoje = timezone.make_aware(timezone.datetime.combine(hoje, timezone.datetime.min.time()))
    fim_hoje = timezone.make_aware(timezone.datetime.combine(hoje, timezone.datetime.max.time()))

    # ========== 2. FILTROS POR LAVANDARIA ==========
    if lavandaria_usuario:
        pedidos_query = Pedido.objects.filter(lavandaria=lavandaria_usuario)
        clientes_query = Cliente.objects.filter(pedidos__lavandaria=lavandaria_usuario).distinct()
    else:
        pedidos_query = Pedido.objects.all()
        clientes_query = Cliente.objects.all()

    # ========== 3. MÉTRICAS PRINCIPAIS ==========

    # Pedidos e receita de hoje
    pedidos_hoje_stats = pedidos_query.filter(criado_em__range=[inicio_hoje, fim_hoje]).aggregate(
        total_pedidos=Count('id'),
        total_receita=Coalesce(Sum('total_pago'), Value(Decimal('0.00')))
    )
    total_pedidos_hoje = pedidos_hoje_stats['total_pedidos']
    receita_hoje = pedidos_hoje_stats['total_receita']

    # Valor médio por pedido (antigo ticket médio)
    valor_medio_pedido = pedidos_query.aggregate(
        media=Coalesce(Avg('total_pago'), Value(Decimal('0.00')))
    )['media']

    # Contagens por status
    status_counts = pedidos_query.values('status').annotate(total=Count('id'))
    status_dict = {item['status']: item['total'] for item in status_counts}

    pedidos_pendentes = status_dict.get('pendente', 0)
    pedidos_completos = status_dict.get('completo', 0)
    pedidos_prontos = status_dict.get('pronto', 0)
    pedidos_entregues = status_dict.get('entregue', 0)

    # Taxa de conclusão
    total_pedidos = pedidos_query.count()
    taxa_conclusao = ((pedidos_entregues + pedidos_prontos) / total_pedidos * 100) if total_pedidos > 0 else 0

    # Pedidos em atraso
    limite_atraso = timezone.now() - timedelta(days=3)
    pedidos_atraso = pedidos_query.filter(
        status='pendente',
        criado_em__lte=limite_atraso
    ).count()

    # Clientes activos (grafia Moçambicana)
    ultimos_30_dias_inicio = timezone.make_aware(
        timezone.datetime.combine(hoje - timedelta(days=30), timezone.datetime.min.time()))
    clientes_activos = clientes_query.filter(
        pedidos__criado_em__gte=ultimos_30_dias_inicio
    ).distinct().count()

    # Clientes fiéis
    clientes_fieis = clientes_query.filter(pontos__gt=1000).count()

    # Total de pontos
    total_pontos = clientes_query.aggregate(total=Coalesce(Sum('pontos'), Value(0)))['total']

    # ========== 4. MÉTRICAS FINANCEIRAS ==========

    # Descontos totais
    descontos = pedidos_query.aggregate(
        desconto_fidelidade=Coalesce(Sum('desconto'), Value(Decimal('0.00'))),
        desconto_cabides=Coalesce(Sum('desconto_cabides'), Value(Decimal('0.00'))),
        total_cabides=Coalesce(Sum('cabides_trazidos'), Value(0))
    )

    total_desconto_fidelidade = descontos['desconto_fidelidade']
    total_desconto_cabides = descontos['desconto_cabides']
    total_cabides = descontos['total_cabides']

    # Saldo pendente
    saldo_pendente_total = Decimal('0.00')
    for pedido in pedidos_query.exclude(status_pagamento='pago').only('id', 'total', 'desconto', 'desconto_cabides',
                                                                      'total_pago'):
        saldo_pendente_total += pedido.saldo

    # Métodos de pagamento
    metodos_pagamento = PagamentoPedido.objects.filter(
        pedido__in=pedidos_query
    ).values('metodo_pagamento').annotate(
        total=Coalesce(Sum('valor'), Value(Decimal('0.00'))),
        quantidade=Count('id')
    ).order_by('-total')[:5]

    # ========== 5. GRÁFICOS ==========

    # Dados da semana
    dados_semana = []
    dias_pt = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }

    for i in range(7):
        dia = hoje - timedelta(days=6 - i)
        inicio_dia = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.min.time()))
        fim_dia = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.max.time()))

        stats_dia = pedidos_query.filter(criado_em__range=[inicio_dia, fim_dia]).aggregate(
            receita=Coalesce(Sum('total_pago'), Value(Decimal('0.00'))),
            pedidos=Count('id')
        )

        dados_semana.append({
            'dia': dia.strftime('%A'),
            'dia_curto': dias_pt.get(dia.strftime('%A'), dia.strftime('%a'))[:3],
            'receita': float(stats_dia['receita']),
            'pedidos': stats_dia['pedidos']
        })

    # Top 5 clientes
    if lavandaria_usuario:
        top_clientes_query = Cliente.objects.filter(
            pedidos__lavandaria=lavandaria_usuario
        ).annotate(
            total_gasto=Coalesce(
                Sum('pedidos__total') - Sum('pedidos__desconto') - Sum('pedidos__desconto_cabides'),
                Value(Decimal('0.00'), output_field=DecimalField())
            ),
            total_pedidos=Count('pedidos')
        ).filter(total_gasto__gt=0).order_by('-total_gasto')[:5]
    else:
        top_clientes_query = Cliente.objects.annotate(
            total_gasto=Coalesce(
                Sum('pedidos__total') - Sum('pedidos__desconto') - Sum('pedidos__desconto_cabides'),
                Value(Decimal('0.00'), output_field=DecimalField())
            ),
            total_pedidos=Count('pedidos')
        ).filter(total_gasto__gt=0).order_by('-total_gasto')[:5]

    top_clientes = []
    for cliente in top_clientes_query:
        top_clientes.append({
            'cliente__nome': cliente.nome,
            'cliente__id': cliente.id,
            'total_gasto': float(cliente.total_gasto),
            'total_pedidos': cliente.total_pedidos
        })

    # Top produtos mais vendidos
    top_produtos = ItemServico.objects.filter(
        itens__pedido__in=pedidos_query
    ).annotate(
        total_vendido=Coalesce(Sum('itens__quantidade'), Value(0)),
        receita_total=Coalesce(Sum('itens__preco_total'), Value(0, output_field=DecimalField()))
    ).filter(total_vendido__gt=0).order_by('-total_vendido')[:5]

    # Desempenho por funcionário
    desempenho_funcionarios = pedidos_query.values(
        'funcionario__user__username'
    ).annotate(
        total_pedidos=Count('id'),
        receita_total=Coalesce(Sum('total_pago'), Value(Decimal('0.00')))
    ).order_by('-total_pedidos')[:5]

    # Distribuição de status
    status_data = []
    status_choices = dict(Pedido.STATUS_CHOICES)
    for status_code, status_name in status_choices.items():
        count = status_dict.get(status_code, 0)
        if count > 0:
            status_data.append({
                'status': status_name,
                'quantidade': count,
                'cor': _get_status_color(status_code)
            })

    # ========== 6. ALERTAS ==========
    alertas = []

    # Pontos prestes a expirar
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

    # ========== 7. PEDIDOS RECENTES ==========
    pedidos_recentes = pedidos_query.select_related('cliente').order_by('-criado_em')[:10]
    pedidos_data = []
    for pedido in pedidos_recentes:
        total_itens = pedido.itens.aggregate(total=Coalesce(Sum('quantidade'), Value(0)))['total']
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
        'stats': {
            'pedidos_hoje': total_pedidos_hoje,
            'receita_hoje': f'{float(receita_hoje):,.0f} MT'.replace(',', '.'),
            'valor_medio_pedido': f'{float(valor_medio_pedido):,.0f} MT'.replace(',', '.'),
            'clientes_activos': clientes_activos,
            'clientes_fieis': clientes_fieis,
            'pedidos_atraso': pedidos_atraso,
            'taxa_conclusao': round(taxa_conclusao, 1),
            'total_pontos': total_pontos,
            'saldo_pendente': f'{float(saldo_pendente_total):,.0f} MT'.replace(',', '.'),
            'total_desconto_fidelidade': f'{float(total_desconto_fidelidade):,.0f} MT'.replace(',', '.'),
            'total_desconto_cabides': f'{float(total_desconto_cabides):,.0f} MT'.replace(',', '.'),
            'total_cabides': total_cabides,
        },
        'dados_semana': dados_semana,
        'status_data': status_data,
        'top_clientes': top_clientes,
        'top_produtos': list(top_produtos),
        'desempenho_funcionarios': list(desempenho_funcionarios),
        'metodos_pagamento': list(metodos_pagamento),
        'alertas': alertas,
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