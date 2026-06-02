from django.urls import path
from . import views

urlpatterns = [
    path('funcionarios/', views.ver_funcionarios, name='ver_funcionarios'),

    path('api/funcionarios/listar/', views.listar_funcionarios),
    path('api/funcionarios/lavandarias/', views.listar_lavandarias_options),
    path('api/funcionarios/cargos/', views.listar_cargos),
    path('api/funcionarios/cargos/permissoes/', views.listar_permissoes_por_cargo),
    path('api/funcionarios/usuarios-disponiveis/', views.listar_usuarios_disponiveis),
    path('api/funcionarios/criar/', views.criar_funcionario),
    path('api/funcionarios/editar/<int:id>/', views.editar_funcionario),
    path('api/funcionarios/excluir/<int:id>/', views.excluir_funcionario),
    path('api/funcionarios/estatisticas/', views.estatisticas_funcionarios),
]
