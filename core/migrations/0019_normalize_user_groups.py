from django.db import migrations


GROUP_ALIASES = {
    'caixa': 'vendedor',
    'Vendedor': 'vendedor',
    'Gerente': 'gerente',
    'Admin': 'admin',
    'SuperUser': 'superuser',
}


def _get_or_merge_group(Group, old_name, new_name):
    old_group = Group.objects.filter(name=old_name).first()
    new_group, _ = Group.objects.get_or_create(name=new_name)

    if old_group and old_group.pk != new_group.pk:
        new_group.permissions.add(*old_group.permissions.all())
        for user in old_group.user_set.all():
            user.groups.add(new_group)
        old_group.delete()

    return new_group


def normalize_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Funcionario = apps.get_model('core', 'Funcionario')

    for old_name, new_name in GROUP_ALIASES.items():
        _get_or_merge_group(Group, old_name, new_name)

    for name in ['vendedor', 'gerente', 'admin', 'superuser']:
        Group.objects.get_or_create(name=name)

    niveis = {
        'vendedor': 1,
        'gerente': 2,
        'admin': 3,
        'superuser': 4,
    }

    for funcionario in Funcionario.objects.select_related('user').all():
        grupo = GROUP_ALIASES.get(funcionario.grupo, funcionario.grupo)
        if grupo not in niveis:
            if funcionario.user.is_superuser:
                grupo = 'superuser'
            elif funcionario.user.is_staff:
                grupo = 'admin'
            else:
                grupo = 'vendedor'

        funcionario.grupo = grupo
        funcionario.nivel_acesso = niveis[grupo]
        funcionario.save(update_fields=['grupo', 'nivel_acesso'])

        group = Group.objects.get(name=grupo)
        funcionario.user.groups.set([group])
        funcionario.user.is_staff = grupo in ['admin', 'superuser']
        funcionario.user.is_superuser = grupo == 'superuser'
        funcionario.user.save(update_fields=['is_staff', 'is_superuser'])

    for user in User.objects.filter(funcionario__isnull=True):
        if not user.is_superuser:
            user.is_staff = False
            user.save(update_fields=['is_staff'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_funcionario_nivel_acesso_alter_funcionario_grupo'),
    ]

    operations = [
        migrations.RunPython(normalize_groups, migrations.RunPython.noop),
    ]
