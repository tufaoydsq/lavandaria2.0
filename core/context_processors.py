from core.decorators import get_user_level


def user_level(request):
    if request.user.is_authenticated:
        return {
            'user_level': get_user_level(request.user),
            'is_superuser': request.user.is_superuser,
            'is_admin': request.user.is_staff,
            'is_gerente': hasattr(request.user, 'funcionario') and request.user.funcionario.grupo == 'gerente',
            'is_vendedor': hasattr(request.user, 'funcionario') and request.user.funcionario.grupo == 'vendedor',
        }
    return {
        'user_level': None,
        'is_superuser': False,
        'is_admin': False,
        'is_gerente': False,
        'is_vendedor': False,
    }
