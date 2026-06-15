from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json

from core.decorators import admin_required
from core.models import Lavandaria, Funcionario, Pedido
from django.db.models import Sum, Count, Q


@login_required
@admin_required
def ver_lavandarias(request):
    """
    View para página de gerenciamento de lavandarias
    """
    return render(request, 'lavandarias/lavandarias.html')

@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def listar_lavandarias(request):
    """
    API: Listar todas as lavandarias
    """
    lavandarias = Lavandaria.objects.all().order_by('-id')

    lavandarias_data = []
    for lav in lavandarias:
        # Contar funcionários
        total_funcionarios = Funcionario.objects.filter(lavandaria=lav).count()

        # Contar pedidos do mês atual
        agora = timezone.now()
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pedidos_mes = Pedido.objects.filter(
            lavandaria=lav,
            criado_em__gte=inicio_mes
        ).count()

        # Calcular receita total (usando total_pago)
        receita_total = Pedido.objects.filter(lavandaria=lav).aggregate(
            total=Sum('total_pago')
        )['total'] or Decimal('0.00')

        lavandarias_data.append({
            'id': lav.id,
            'nome': lav.nome,
            'endereco': lav.endereco,
            'telefone': lav.telefone,
            'criado_em': lav.criado_em.strftime('%Y-%m-%d'),
            'funcionarios': total_funcionarios,
            'pedidos_mes': pedidos_mes,
            'receita_total': float(receita_total)
        })

    return JsonResponse({'success': True, 'lavandarias': lavandarias_data})

@csrf_exempt
@require_http_methods(["POST"])
@login_required
@admin_required
def criar_lavandaria(request):
    """
    API: Criar nova lavandaria
    """
    try:
        data = json.loads(request.body)
        nome = data.get('nome')
        endereco = data.get('endereco')
        telefone = data.get('telefone')

        if not nome:
            return JsonResponse({'success': False, 'error': 'Nome é obrigatório'}, status=400)
        if not endereco:
            return JsonResponse({'success': False, 'error': 'Endereço é obrigatório'}, status=400)
        if not telefone:
            return JsonResponse({'success': False, 'error': 'Telefone é obrigatório'}, status=400)

        # Verificar se telefone já existe
        if Lavandaria.objects.filter(telefone=telefone).exists():
            return JsonResponse({'success': False, 'error': 'Telefone já cadastrado'}, status=400)

        lavandaria = Lavandaria.objects.create(
            nome=nome,
            endereco=endereco,
            telefone=telefone
        )

        return JsonResponse({
            'success': True,
            'lavandaria': {
                'id': lavandaria.id,
                'nome': lavandaria.nome,
                'endereco': lavandaria.endereco,
                'telefone': lavandaria.telefone,
                'criado_em': lavandaria.criado_em.strftime('%Y-%m-%d'),
                'funcionarios': 0,
                'pedidos_mes': 0,
                'receita_total': 0
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["PUT"])
@login_required
@admin_required
def editar_lavandaria(request, id):
    """
    API: Editar lavandaria existente
    """
    try:
        lavandaria = get_object_or_404(Lavandaria, id=id)
        data = json.loads(request.body)

        if 'nome' in data:
            lavandaria.nome = data['nome']
        if 'endereco' in data:
            lavandaria.endereco = data['endereco']
        if 'telefone' in data:
            telefone = data['telefone']
            # Verificar se telefone já existe (exceto para esta lavandaria)
            if Lavandaria.objects.filter(telefone=telefone).exclude(id=id).exists():
                return JsonResponse({'success': False, 'error': 'Telefone já cadastrado'}, status=400)
            lavandaria.telefone = telefone

        lavandaria.save()

        # Recalcular estatísticas
        total_funcionarios = Funcionario.objects.filter(lavandaria=lavandaria).count()
        agora = timezone.now()
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pedidos_mes = Pedido.objects.filter(
            lavandaria=lavandaria,
            criado_em__gte=inicio_mes
        ).count()
        receita_total = Pedido.objects.filter(lavandaria=lavandaria).aggregate(
            total=Sum('total_pago')
        )['total'] or Decimal('0.00')

        return JsonResponse({
            'success': True,
            'lavandaria': {
                'id': lavandaria.id,
                'nome': lavandaria.nome,
                'endereco': lavandaria.endereco,
                'telefone': lavandaria.telefone,
                'criado_em': lavandaria.criado_em.strftime('%Y-%m-%d'),
                'funcionarios': total_funcionarios,
                'pedidos_mes': pedidos_mes,
                'receita_total': float(receita_total)
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
@admin_required
def excluir_lavandaria(request, id):
    """
    API: Excluir lavandaria
    """
    try:
        lavandaria = get_object_or_404(Lavandaria, id=id)

        # Verificar se existem funcionários ou pedidos associados
        tem_funcionarios = Funcionario.objects.filter(lavandaria=lavandaria).exists()
        tem_pedidos = Pedido.objects.filter(lavandaria=lavandaria).exists()

        if tem_funcionarios or tem_pedidos:
            return JsonResponse({
                'success': False,
                'error': 'Não é possível excluir esta lavandaria pois existem funcionários ou pedidos associados.'
            }, status=400)

        nome = lavandaria.nome
        lavandaria.delete()

        return JsonResponse({
            'success': True,
            'message': f'Lavandaria "{nome}" excluída com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def estatisticas_lavandarias(request):
    """
    API: Obter estatísticas gerais das lavandarias
    """
    try:
        total_lavandarias = Lavandaria.objects.count()
        total_funcionarios = Funcionario.objects.count()

        # Pedidos do mês atual
        agora = timezone.now()
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total_pedidos_mes = Pedido.objects.filter(
            criado_em__gte=inicio_mes
        ).count()

        # Receita total
        receita_total = Pedido.objects.aggregate(
            total=Sum('total_pago')
        )['total'] or Decimal('0.00')

        return JsonResponse({
            'success': True,
            'estatisticas': {
                'total_lavandarias': total_lavandarias,
                'total_funcionarios': total_funcionarios,
                'total_pedidos_mes': total_pedidos_mes,
                'receita_total': float(receita_total)
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def detalhes_lavandaria(request, id):
    """
    API: Obter detalhes completos de uma lavandaria
    """
    try:
        lavandaria = get_object_or_404(Lavandaria, id=id)

        # Funcionários
        funcionarios = Funcionario.objects.filter(lavandaria=lavandaria).select_related('user')
        funcionarios_list = []
        for func in funcionarios:
            funcionarios_list.append({
                'id': func.id,
                'nome': func.user.get_full_name() or func.user.username,
                'username': func.user.username,
                'grupo': func.grupo,
                'telefone': func.telefone or ''
            })

        return JsonResponse({
            'success': True,
            'detalhes': {
                'id': lavandaria.id,
                'nome': lavandaria.nome,
                'endereco': lavandaria.endereco,
                'telefone': lavandaria.telefone,
                'criado_em': lavandaria.criado_em.strftime('%d/%m/%Y %H:%M'),
                'funcionarios': funcionarios_list,
                'total_funcionarios': len(funcionarios_list),
                'total_pedidos': Pedido.objects.filter(lavandaria=lavandaria).count(),
                'receita_total': float(
                    Pedido.objects.filter(lavandaria=lavandaria).aggregate(total=Sum('total_pago'))['total'] or 0)
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
