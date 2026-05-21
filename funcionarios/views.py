from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User, Group
from django.utils import timezone
import json
from core.models import Funcionario, Lavandaria


def ver_funcionarios(request):
    """
    View para página de gerenciamento de funcionários
    """
    return render(request, 'funcionarios/funcionarios.html')


@csrf_exempt
@require_http_methods(["GET"])
def listar_funcionarios(request):
    """
    API: Listar todos os funcionários
    """
    funcionarios = Funcionario.objects.select_related('user', 'lavandaria').all().order_by('-id')

    funcionarios_data = []
    for func in funcionarios:
        funcionarios_data.append({
            'id': func.id,
            'user_id': func.user.id,
            'nome': func.user.get_full_name() or func.user.username,
            'username': func.user.username,
            'telefone': func.telefone or '',
            'cargo': func.grupo,
            'lavandaria_id': func.lavandaria.id,
            'lavandaria_nome': func.lavandaria.nome,
            'ativo': func.user.is_active,
            'ultimo_acesso': func.user.last_login.strftime('%Y-%m-%d %H:%M:%S') if func.user.last_login else None,
            'criado_em': func.user.date_joined.strftime('%Y-%m-%d')
        })

    return JsonResponse({'success': True, 'funcionarios': funcionarios_data})


@csrf_exempt
@require_http_methods(["GET"])
def listar_usuarios_disponiveis(request):
    """
    API: Listar usuários disponíveis para associar como funcionário
    """
    # Usuários que não são funcionários ainda
    usuarios_funcionarios = Funcionario.objects.values_list('user_id', flat=True)
    usuarios_disponiveis = User.objects.exclude(id__in=usuarios_funcionarios).filter(is_staff=True)

    usuarios_data = []
    for user in usuarios_disponiveis:
        usuarios_data.append({
            'id': user.id,
            'nome': user.get_full_name() or user.username,
            'username': user.username,
            'email': user.email
        })

    return JsonResponse({'success': True, 'usuarios': usuarios_data})


@csrf_exempt
@require_http_methods(["GET"])
def listar_lavandarias_options(request):
    """
    API: Listar lavandarias para o select
    """
    lavandarias = Lavandaria.objects.all().values('id', 'nome')
    return JsonResponse({'success': True, 'lavandarias': list(lavandarias)})


@csrf_exempt
@require_http_methods(["POST"])
def criar_funcionario(request):
    """
    API: Associar um usuário existente a uma lavandaria como funcionário
    """
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        lavandaria_id = data.get('lavandaria_id')
        telefone = data.get('telefone', '')
        grupo = data.get('grupo')

        # Validações
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Usuário é obrigatório'}, status=400)
        if not grupo:
            return JsonResponse({'success': False, 'error': 'Cargo é obrigatório'}, status=400)
        if not lavandaria_id:
            return JsonResponse({'success': False, 'error': 'Lavandaria é obrigatória'}, status=400)

        # Verificar se usuário existe
        user = get_object_or_404(User, id=user_id)

        # Verificar se usuário já é funcionário
        if Funcionario.objects.filter(user=user).exists():
            return JsonResponse({'success': False, 'error': 'Usuário já é funcionário'}, status=400)

        # Obter lavandaria
        lavandaria = get_object_or_404(Lavandaria, id=lavandaria_id)

        # Criar funcionário
        funcionario = Funcionario.objects.create(
            user=user,
            lavandaria=lavandaria,
            telefone=telefone,
            grupo=grupo
        )

        return JsonResponse({
            'success': True,
            'message': f'Funcionário {user.get_full_name() or user.username} criado com sucesso!',
            'funcionario': {
                'id': funcionario.id,
                'user_id': user.id,
                'nome': user.get_full_name() or user.username,
                'username': user.username,
                'telefone': funcionario.telefone,
                'cargo': funcionario.grupo,
                'lavandaria_id': lavandaria.id,
                'lavandaria_nome': lavandaria.nome,
                'ativo': user.is_active,
                'criado_em': user.date_joined.strftime('%Y-%m-%d')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
def editar_funcionario(request, id):
    """
    API: Editar funcionário existente
    """
    try:
        funcionario = get_object_or_404(Funcionario, id=id)
        data = json.loads(request.body)

        if 'telefone' in data:
            funcionario.telefone = data['telefone']

        if 'grupo' in data:
            funcionario.grupo = data['grupo']
            # Atualizar grupo do usuário
            grupo = Group.objects.get(name=data['grupo'])
            funcionario.user.groups.set([grupo])

        if 'lavandaria_id' in data:
            lavandaria = get_object_or_404(Lavandaria, id=data['lavandaria_id'])
            funcionario.lavandaria = lavandaria

        if 'ativo' in data:
            funcionario.user.is_active = data['ativo']
            funcionario.user.save()

        funcionario.save()

        return JsonResponse({
            'success': True,
            'message': 'Funcionário atualizado com sucesso!',
            'funcionario': {
                'id': funcionario.id,
                'user_id': funcionario.user.id,
                'nome': funcionario.user.get_full_name() or funcionario.user.username,
                'username': funcionario.user.username,
                'telefone': funcionario.telefone,
                'cargo': funcionario.grupo,
                'lavandaria_id': funcionario.lavandaria.id,
                'lavandaria_nome': funcionario.lavandaria.nome,
                'ativo': funcionario.user.is_active,
                'criado_em': funcionario.user.date_joined.strftime('%Y-%m-%d')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def excluir_funcionario(request, id):
    """
    API: Excluir funcionário (apenas a associação, não o usuário)
    """
    try:
        funcionario = get_object_or_404(Funcionario, id=id)
        nome = funcionario.user.get_full_name() or funcionario.user.username
        funcionario.delete()

        return JsonResponse({
            'success': True,
            'message': f'Funcionário "{nome}" removido com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
def estatisticas_funcionarios(request):
    """
    API: Obter estatísticas dos funcionários
    """
    try:
        total_funcionarios = Funcionario.objects.count()
        ativos = Funcionario.objects.filter(user__is_active=True).count()
        inativos = total_funcionarios - ativos
        gerentes = Funcionario.objects.filter(grupo='gerente').count()
        caixas = Funcionario.objects.filter(grupo='caixa').count()

        return JsonResponse({
            'success': True,
            'estatisticas': {
                'total': total_funcionarios,
                'ativos': ativos,
                'inativos': inativos,
                'gerentes': gerentes,
                'caixas': caixas
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)