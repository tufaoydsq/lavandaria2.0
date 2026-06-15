from django import template

register = template.Library()


@register.filter
def ljust(value, length):
    return str(value).ljust(int(length))


@register.filter
def sum_values(queryset, field_name):
    return sum(getattr(item, field_name, 0) or 0 for item in queryset)


@register.filter
def sum_pagos(queryset, campo):
    return sum(getattr(item, campo, 0) or 0 for item in queryset if getattr(item, 'pago', False))


@register.filter
def sum_nao_pagos(queryset, campo):
    return sum(getattr(item, campo, 0) or 0 for item in queryset if not getattr(item, 'pago', False))


@register.filter
def currency_mzn(value):
    try:
        return f"{float(value):,.2f} MZN".replace(",", " ")
    except (TypeError, ValueError):
        return "0.00 MZN"
