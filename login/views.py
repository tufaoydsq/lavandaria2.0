from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
import secrets
import json


def login_view(request):
    """
    View para página de login (aceita GET e POST)
    """
    if request.user.is_authenticated:
        return redirect('ver_dashboard')

    # Processar POST (login)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me') == 'on'

        # Autenticar usuário
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Configurar sessão
            if not remember_me:
                request.session.set_expiry(0)  # Expira ao fechar navegador
            else:
                request.session.set_expiry(1209600)  # 2 semanas

            # Verificar permissão
            if user.is_staff or hasattr(user, 'funcionario'):
                return redirect('ver_dashboard')
            else:
                messages.warning(request, 'Você não tem permissão para acessar o sistema')
                logout(request)
                return redirect('login')
        else:
            messages.error(request, 'Username ou senha incorretos')
            return redirect('login')

    # GET - mostrar formulário
    return render(request, 'login/login.html')


def do_login(request):
    """
    View separada para login (redireciona para login_view)
    """
    return login_view(request)


def logout_view(request):
    """
    Logout do usuário
    """
    logout(request)
    messages.success(request, 'Você saiu do sistema com sucesso!')
    return redirect('login')


@csrf_exempt
@require_http_methods(["POST"])
def password_reset_request(request):
    """
    API: Solicitar reset de senha
    """
    try:
        data = json.loads(request.body)
        email = data.get('email')

        if not email:
            return JsonResponse({'success': False, 'error': 'Email é obrigatório'}, status=400)

        # Buscar usuário pelo email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Por segurança, não informar que o email não existe
            return JsonResponse({'success': True, 'message': 'Se o email existir, enviaremos o link de recuperação'})

        # Gerar token
        token = secrets.token_urlsafe(32)

        # Link de recuperação
        reset_link = f"{request.build_absolute_uri('/')}reset-password/?token={token}"

        # Em produção, você deve enviar por email
        print(f"🔐 Link de recuperação para {user.email}: {reset_link}")

        return JsonResponse({'success': True, 'message': 'Link de recuperação enviado para seu email'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)