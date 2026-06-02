from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from core.decorators import admin_required
import json


@login_required
@admin_required
def ver_user(request):
    """
    View para página de gestão de utilizadores
    """
    return render(request, 'user/user.html')


@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def listar_usuarios(request):
    """
    API: Listar todos os utilizadores
    """
    usuarios = User.objects.all().order_by('-id')

    usuarios_data = []
    for user in usuarios:
        usuarios_data.append({
            'id': user.id,
            'name': user.get_full_name() or user.username,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'last_access': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
            'date_joined': user.date_joined.strftime('%Y-%m-%d')
        })

    return JsonResponse({'success': True, 'usuarios': usuarios_data})


@csrf_exempt
@require_http_methods(["POST"])
@login_required
@admin_required
def criar_usuario(request):
    """
    API: Criar novo utilizador (apenas dados básicos)
    """
    try:
        data = json.loads(request.body)
        name = data.get('name', '')
        username = data.get('username')
        email = data.get('email')
        is_active = data.get('is_active', True)
        is_staff = data.get('is_staff', False) if request.user.is_superuser else False
        is_superuser = data.get('is_superuser', False) if request.user.is_superuser else False
        password = data.get('password', '')

        # Validações
        if not username:
            return JsonResponse({'success': False, 'error': 'Username é obrigatório'}, status=400)
        if not email:
            return JsonResponse({'success': False, 'error': 'Email é obrigatório'}, status=400)

        # Verificar se username já existe
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'error': 'Username já existe'}, status=400)

        # Verificar se email já existe
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'Email já existe'}, status=400)

        # Gerar senha se não for fornecida
        if not password:
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(alphabet) for _ in range(10))

        # Separar nome e sobrenome
        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Criar usuário
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser
        )
        user.set_password(password)
        user.save()

        return JsonResponse({
            'success': True,
            'message': f'Utilizador {username} criado com sucesso!',
            'senha_temporaria': password,
            'usuario': {
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
@login_required
@admin_required
def editar_usuario(request, id):
    """
    API: Editar utilizador existente
    """
    try:
        user = get_object_or_404(User, id=id)
        data = json.loads(request.body)
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Apenas superusuarios podem editar outro superusuario'}, status=403)

        # Atualizar dados básicos
        if 'name' in data:
            name_parts = data['name'].split(' ', 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ''

        if 'username' in data and data['username'] != user.username:
            if User.objects.filter(username=data['username']).exists():
                return JsonResponse({'success': False, 'error': 'Username já existe'}, status=400)
            user.username = data['username']

        if 'email' in data and data['email'] != user.email:
            if User.objects.filter(email=data['email']).exists():
                return JsonResponse({'success': False, 'error': 'Email já existe'}, status=400)
            user.email = data['email']

        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'is_staff' in data and request.user.is_superuser:
            user.is_staff = data['is_staff']
        if 'is_superuser' in data and request.user.is_superuser:
            user.is_superuser = data['is_superuser']

        if 'password' in data and data['password']:
            user.set_password(data['password'])

        user.save()

        return JsonResponse({
            'success': True,
            'message': 'Utilizador atualizado com sucesso!',
            'usuario': {
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
@admin_required
def resetar_senha_usuario(request, id):
    """
    API: Resetar senha do utilizador
    """
    try:
        user = get_object_or_404(User, id=id)
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Apenas superusuarios podem resetar senha de outro superusuario'}, status=403)

        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        nova_senha = ''.join(secrets.choice(alphabet) for _ in range(10))

        user.set_password(nova_senha)
        user.save()

        return JsonResponse({
            'success': True,
            'message': 'Senha resetada com sucesso!',
            'nova_senha': nova_senha
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PATCH"])
@login_required
@admin_required
def toggle_status_usuario(request, id):
    """
    API: Alternar status do utilizador (ativar/desativar)
    """
    try:
        user = get_object_or_404(User, id=id)
        if user == request.user:
            return JsonResponse({'success': False, 'error': 'Nao pode alterar o estado do proprio utilizador'}, status=400)
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Apenas superusuarios podem alterar outro superusuario'}, status=403)
        data = json.loads(request.body)
        is_active = data.get('is_active', False)

        user.is_active = is_active
        user.save()

        return JsonResponse({
            'success': True,
            'message': f'Utilizador {user.username} {"ativado" if is_active else "desativado"} com sucesso',
            'is_active': is_active
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
@admin_required
def excluir_usuario(request, id):
    """
    API: Excluir utilizador
    """
    try:
        user = get_object_or_404(User, id=id)
        if user == request.user:
            return JsonResponse({'success': False, 'error': 'Nao pode excluir o proprio utilizador'}, status=400)
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Apenas superusuarios podem excluir outro superusuario'}, status=403)
        username = user.username
        user.delete()

        return JsonResponse({
            'success': True,
            'message': f'Utilizador "{username}" excluído com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
@admin_required
def estatisticas_usuarios(request):
    """
    API: Obter estatísticas dos utilizadores
    """
    try:
        total = User.objects.count()
        ativos = User.objects.filter(is_active=True).count()
        staff = User.objects.filter(is_staff=True).count()
        superusers = User.objects.filter(is_superuser=True).count()

        return JsonResponse({
            'success': True,
            'estatisticas': {
                'total': total,
                'ativos': ativos,
                'staff': staff,
                'superusers': superusers
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
