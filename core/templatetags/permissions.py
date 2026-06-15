from django import template

register = template.Library()


@register.filter
def has_group(user, group_name):
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter
def has_level(user, level):
    if not user.is_authenticated:
        return False

    niveis = {
        'superuser': 4,
        'admin': 3,
        'gerente': 2,
        'vendedor': 1,
    }

    if user.is_superuser:
        user_level = 4
    elif user.is_staff:
        user_level = 3
    elif hasattr(user, 'funcionario') and user.funcionario.grupo:
        user_level = niveis.get(user.funcionario.grupo, 0)
    else:
        user_level = 0

    return user_level >= int(level)


@register.simple_tag
def show_for_group(group_name, user):
    allowed_groups = [g.strip() for g in group_name.split(',')]
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=allowed_groups).exists()


@register.filter
def can_edit(user):
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, 'funcionario') and user.funcionario.grupo in ['gerente', 'admin']


@register.filter
def can_delete(user):
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, 'funcionario') and user.funcionario.grupo == 'admin'
