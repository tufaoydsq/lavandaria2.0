# scripts/criar_grupos.py
import os
import sys
from pathlib import Path
import django

# Adicionar o caminho do projeto
sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'powerWashing.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.models import Pedido, Cliente, ItemServico, Funcionario, Lavandaria


def criar_grupos():
    """
    Função para criar os grupos automaticamente
    """
    grupos = {
        'vendedor': {
            'models': ['pedido', 'cliente'],
            'actions': ['add', 'change', 'view']
        },
        'gerente': {
            'models': ['pedido', 'cliente', 'itemservico'],
            'actions': ['add', 'change', 'view', 'delete']
        },
        'admin': {
            'models': ['pedido', 'cliente', 'itemservico', 'funcionario', 'lavandaria'],
            'actions': ['add', 'change', 'view', 'delete']
        },
        'superuser': {
            'models': ['pedido', 'cliente', 'itemservico', 'funcionario', 'lavandaria'],
            'actions': ['add', 'change', 'view', 'delete']
        },
    }

    model_map = {
        'pedido': Pedido,
        'cliente': Cliente,
        'itemservico': ItemServico,
        'funcionario': Funcionario,
        'lavandaria': Lavandaria,
    }

    print("\n🔧 Criando grupos de permissões...\n")

    for grupo_nome, config in grupos.items():
        grupo, created = Group.objects.get_or_create(name=grupo_nome)

        if created:
            print(f"✅ Criando grupo: {grupo_nome}")
        else:
            print(f"📝 Atualizando grupo: {grupo_nome}")

        for model_name in config['models']:
            model = model_map.get(model_name)
            if not model:
                continue

            content_type = ContentType.objects.get_for_model(model)

            for action in config['actions']:
                codename = f"{action}_{model_name}"
                try:
                    permission = Permission.objects.get(
                        codename=codename,
                        content_type=content_type
                    )
                    grupo.permissions.add(permission)
                    print(f"  ✓ Adicionada: {codename}")
                except Permission.DoesNotExist:
                    print(f"  ✗ Não encontrada: {codename}")

    print("\n🎉 Grupos criados/atualizados com sucesso!")


if __name__ == "__main__":
    criar_grupos()
