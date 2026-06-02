# core/templatetags/permissions.py
from django import template
from django.contrib.auth.models import Group

register = template.Library()


@register.filter
def has_group(user, group_name):
    """
    Verifica se o usuário pertence a um grupo específico
    Uso: {% if user|has_group:'gerente' %}
    """
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter
def has_level(user, level):
    """
    Verifica se o usuário tem um nível mínimo de acesso
    levels: 1=vendedor, 2=gerente, 3=admin, 4=superuser
    Uso: {% if user|has_level:2 %}
    """
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
        user_level = niveis.get(user.funcionario.grupo, 1)
    else:
        user_level = 1

    return user_level >= level


@register.simple_tag
def show_for_group(group_name, user):
    """
    Mostra conteúdo apenas para grupos específicos
    Uso: {% show_for_group 'admin,gerente' user %}
        Conteúdo apenas para admin e gerente
    {% endshow_for_group %}
    """
    allowed_groups = [g.strip() for g in group_name.split(',')]
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=allowed_groups).exists()


@register.filter
def can_edit(user):
    """Verifica se o usuário pode editar (gerente ou superior)"""
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, 'funcionario') and user.funcionario.grupo in ['gerente', 'admin']


@register.filter
def can_delete(user):
    """Verifica se o usuário pode excluir (admin ou superior)"""
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, 'funcionario') and user.funcionario.grupo == 'admin'