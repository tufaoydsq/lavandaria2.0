from django.urls import path
from . import views

urlpatterns = [
    path('funcionarios/', views.ver_funcionarios, name='ver_funcionarios'),
    path('api/funcionarios/', views.listar_funcionarios, name='listar_funcionarios'),
    path('api/funcionarios/usuarios-disponiveis/', views.listar_usuarios_disponiveis, name='listar_usuarios_disponiveis'),
    path('api/funcionarios/lavandarias/', views.listar_lavandarias_options, name='listar_lavandarias_options'),
    path('api/funcionarios/criar/', views.criar_funcionario, name='criar_funcionario'),
    path('api/funcionarios/editar/<int:id>/', views.editar_funcionario, name='editar_funcionario'),
    path('api/funcionarios/excluir/<int:id>/', views.excluir_funcionario, name='excluir_funcionario'),
    path('api/funcionarios/estatisticas/', views.estatisticas_funcionarios, name='estatisticas_funcionarios'),
]