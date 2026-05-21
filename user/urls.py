from django.urls import path
from . import views

urlpatterns = [
    # Página principal
    path('user/', views.ver_user, name='ver_user'),

    # APIs para utilizadores
    path('api/usuarios/', views.listar_usuarios, name='listar_usuarios'),
    path('api/usuarios/criar/', views.criar_usuario, name='criar_usuario'),
    path('api/usuarios/editar/<int:id>/', views.editar_usuario, name='editar_usuario'),
    path('api/usuarios/resetar-senha/<int:id>/', views.resetar_senha_usuario, name='resetar_senha_usuario'),
    path('api/usuarios/toggle-status/<int:id>/', views.toggle_status_usuario, name='toggle_status_usuario'),
    path('api/usuarios/excluir/<int:id>/', views.excluir_usuario, name='excluir_usuario'),
    path('api/usuarios/estatisticas/', views.estatisticas_usuarios, name='estatisticas_usuarios'),
]