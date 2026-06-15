from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def login_required_message(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faca login para acessar o sistema.')
            return redirect('login')
        return view_func(request, *args, **kwargs)

    return wrapper


def vendedor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faca login para acessar o sistema.')
            return redirect('login')

        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)

        if hasattr(request.user, 'funcionario') and request.user.funcionario.grupo == 'vendedor':
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Voce nao tem permissao para acessar esta pagina.')
        return redirect('ver_dashboard')

    return wrapper


def gerente_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faca login para acessar o sistema.')
            return redirect('login')

        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)

        if hasattr(request.user, 'funcionario') and request.user.funcionario.grupo == 'gerente':
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Apenas gerentes tem permissao para acessar esta pagina.')
        return redirect('ver_dashboard')

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faca login para acessar o sistema.')
            return redirect('login')

        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Apenas administradores tem permissao para acessar esta pagina.')
        return redirect('ver_dashboard')

    return wrapper


def superuser_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faca login para acessar o sistema.')
            return redirect('login')

        if not request.user.is_superuser:
            messages.error(request, 'Apenas superusuarios tem permissao para acessar esta pagina.')
            return redirect('ver_dashboard')

        return view_func(request, *args, **kwargs)

    return wrapper


def get_user_level(user):
    if user.is_superuser:
        return 'superuser'
    if user.is_staff:
        return 'admin'
    if hasattr(user, 'funcionario'):
        if user.funcionario.grupo == 'gerente':
            return 'gerente'
        if user.funcionario.grupo == 'vendedor':
            return 'vendedor'
    return None
