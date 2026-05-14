# api.py
from django.http import JsonResponse
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Pedido


def receita_por_periodo(request):
    """API para buscar dados de receita por período"""
    dias = int(request.GET.get('dias', 7))

    hoje = timezone.now().date()
    inicio_periodo = hoje - timedelta(days=dias - 1)

    dados = []
    for i in range(dias):
        dia = inicio_periodo + timedelta(days=i)
        inicio_dia = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.min.time()))
        fim_dia = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.max.time()))

        receita = Pedido.objects.filter(
            criado_em__range=[inicio_dia, fim_dia]
        ).aggregate(total=Sum('total_pago'))['total'] or Decimal('0.00')

        dados.append({
            'dia': dia.strftime('%a'),
            'valor': float(receita)
        })

    return JsonResponse({
        'dias': [d['dia'] for d in dados],
        'valores': [d['valor'] for d in dados]
    })