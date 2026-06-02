
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def login_required_message(view_func):
    """
    Decorador que redireciona para login com mensagem
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faça login para acessar o sistema.')
            return redirect('login')
        return view_func(request, *args, **kwargs)

    return wrapper


def vendedor_required(view_func):
    """
    Nível 1: Vendedor (Caixa)
    - Pode acessar: Dashboard, Pedidos, Clientes
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faça login para acessar o sistema.')
            return redirect('login')

        # SuperUser e Admin têm acesso total
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        # Verificar se é admin (staff)
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        # Verificar se é funcionário
        if hasattr(request.user, 'funcionario'):
            # Vendedor (caixa) tem acesso
            if request.user.funcionario.grupo == 'vendedor':
                return view_func(request, *args, **kwargs)

        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('ver_dashboard')

    return wrapper


def gerente_required(view_func):
    """
    Nível 2: Gerente
    - Pode acessar: Tudo que o Vendedor acessa + Artigos, Relatórios, Funcionários
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faça login para acessar o sistema.')
            return redirect('login')

        # SuperUser e Admin têm acesso total
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        # Verificar se é gerente
        if hasattr(request.user, 'funcionario') and request.user.funcionario.grupo == 'gerente':
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Apenas gerentes têm permissão para acessar esta página.')
        return redirect('ver_dashboard')

    return wrapper


def admin_required(view_func):
    """
    Nível 3: Admin (Staff)
    - Pode acessar: Tudo que o Gerente acessa + Lavandarias, Configurações
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faça login para acessar o sistema.')
            return redirect('login')

        # SuperUser tem acesso total
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        # Admin (staff) tem acesso
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Apenas administradores têm permissão para acessar esta página.')
        return redirect('ver_dashboard')

    return wrapper


def superuser_required(view_func):
    """
    Nível 4: SuperUser
    - Acesso total ao sistema (todas as funcionalidades)
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, faça login para acessar o sistema.')
            return redirect('login')

        if not request.user.is_superuser:
            messages.error(request, 'Apenas superusuários têm permissão para acessar esta página.')
            return redirect('ver_dashboard')

        return view_func(request, *args, **kwargs)

    return wrapper


def get_user_level(user):
    """
    Função auxiliar para obter o nível de acesso do usuário
    Retorna: 'superuser', 'admin', 'gerente', 'vendedor'
    """
    if user.is_superuser:
        return 'superuser'
    elif user.is_staff:
        return 'admin'
    elif hasattr(user, 'funcionario'):
        if user.funcionario.grupo == 'gerente':
            return 'gerente'
        elif user.funcionario.grupo == 'vendedor':
            return 'vendedor'
    return None
