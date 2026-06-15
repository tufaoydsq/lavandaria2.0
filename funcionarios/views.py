from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User, Group
import json

from core.decorators import admin_required
from core.models import Funcionario, Lavandaria


@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def ver_funcionarios(request):
    return render(request, 'funcionarios/funcionarios.html')


@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def listar_funcionarios(request):
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
@login_required
@admin_required
def listar_usuarios_disponiveis(request):
    usuarios_funcionarios = Funcionario.objects.values_list('user_id', flat=True)
    usuarios_disponiveis = User.objects.exclude(id__in=usuarios_funcionarios).filter(is_active=True)
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
@login_required
@admin_required
def listar_lavandarias_options(request):
    lavandarias = Lavandaria.objects.all().values('id', 'nome')
    return JsonResponse({'success': True, 'lavandarias': list(lavandarias)})


@csrf_exempt
@require_http_methods(["POST"])
@login_required
@admin_required
def criar_funcionario(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        lavandaria_id = data.get('lavandaria_id')
        telefone = data.get('telefone', '')
        grupo = data.get('grupo', '').strip().lower()

        if not user_id:
            return JsonResponse({'success': False, 'error': 'Usuario é obrigatorio'}, status=400)
        if not grupo:
            return JsonResponse({'success': False, 'error': 'Cargo é obrigatorio'}, status=400)
        if not lavandaria_id:
            return JsonResponse({'success': False, 'error': 'Lavandaria é obrigatoria'}, status=400)

        # Validar grupo permitido
        grupos_permitidos = ['vendedor', 'gerente', 'admin', 'superuser']
        if grupo not in grupos_permitidos:
            return JsonResponse({'success': False, 'error': f'Cargo inválido. Use: {grupos_permitidos}'}, status=400)
        if grupo == 'superuser' and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Apenas superusuarios podem criar outro superusuario'}, status=403)

        user = get_object_or_404(User, id=user_id)

        if Funcionario.objects.filter(user=user).exists():
            return JsonResponse({'success': False, 'error': 'Usuario ja é funcionario'}, status=400)

        lavandaria = get_object_or_404(Lavandaria, id=lavandaria_id)
        group, _ = Group.objects.get_or_create(name=grupo)
        user.groups.set([group])

        funcionario = Funcionario.objects.create(
            user=user,
            lavandaria=lavandaria,
            telefone=telefone,
            grupo=grupo
        )

        return JsonResponse({
            'success': True,
            'message': f'Funcionario {user.get_full_name() or user.username} criado com sucesso',
            'funcionario': {
                'id': funcionario.id,
                'nome': user.get_full_name() or user.username,
                'cargo': funcionario.grupo,
                'lavandaria_nome': lavandaria.nome,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
@login_required
@admin_required
def editar_funcionario(request, id):
    try:
        funcionario = get_object_or_404(Funcionario, id=id)
        data = json.loads(request.body)

        if 'telefone' in data:
            funcionario.telefone = data['telefone']

        if 'grupo' in data and data['grupo']:
            grupo_nome = data['grupo'].strip().lower()
            grupos_permitidos = ['vendedor', 'gerente', 'admin', 'superuser']
            if grupo_nome not in grupos_permitidos:
                return JsonResponse({'success': False, 'error': f'Cargo invalido. Use: {grupos_permitidos}'}, status=400)
            if grupo_nome == 'superuser' and not request.user.is_superuser:
                return JsonResponse({'success': False, 'error': 'Apenas superusuarios podem atribuir esse cargo'}, status=403)
            grupo, _ = Group.objects.get_or_create(name=grupo_nome)
            funcionario.grupo = grupo_nome
            funcionario.user.groups.set([grupo])

        if 'lavandaria_id' in data:
            lavandaria = get_object_or_404(Lavandaria, id=data['lavandaria_id'])
            funcionario.lavandaria = lavandaria

        if 'ativo' in data:
            funcionario.user.is_active = data['ativo']
            funcionario.user.save()

        funcionario.save()

        return JsonResponse({'success': True, 'message': 'Funcionario atualizado com sucesso'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
@admin_required
def excluir_funcionario(request, id):
    try:
        funcionario = get_object_or_404(Funcionario, id=id)
        nome = funcionario.user.get_full_name() or funcionario.user.username
        funcionario.delete()
        return JsonResponse({'success': True, 'message': f'Funcionario "{nome}" removido com sucesso'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def estatisticas_funcionarios(request):
    try:
        total_funcionarios = Funcionario.objects.count()
        ativos = Funcionario.objects.filter(user__is_active=True).count()
        inativos = total_funcionarios - ativos

        # ✅ Grupos correctos conforme o seu sistema
        vendedores = Funcionario.objects.filter(grupo='vendedor').count()
        gerentes = Funcionario.objects.filter(grupo='gerente').count()
        admins = User.objects.filter(is_staff=True, is_superuser=False).count()
        superusers = User.objects.filter(is_superuser=True).count()

        return JsonResponse({
            'success': True,
            'estatisticas': {
                'total': total_funcionarios,
                'ativos': ativos,
                'inativos': inativos,
                'vendedores': vendedores,
                'gerentes': gerentes,
                'admins': admins,
                'superusers': superusers
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def listar_cargos(request):
    try:
        grupos = Group.objects.all().values('id', 'name')
        return JsonResponse({'success': True, 'cargos': list(grupos)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def listar_permissoes_por_cargo(request):
    try:
        cargo_nome = request.GET.get('cargo')
        if not cargo_nome:
            return JsonResponse({'success': False, 'error': 'Cargo é obrigatorio'}, status=400)

        try:
            grupo = Group.objects.get(name=cargo_nome)
            permissoes = list(grupo.permissions.values_list('name', flat=True))
        except Group.DoesNotExist:
            permissoes = []

        return JsonResponse({'success': True, 'permissoes': permissoes})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
