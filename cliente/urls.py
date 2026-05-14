from django.urls import path
from . import views

urlpatterns = [
    # Página principal de clientes
    path('cliente/', views.ver_cliente, name='ver_cliente'),

    # APIs para clientes
    path('api/clientes/', views.listar_clientes, name='listar_clientes'),
    path('api/clientes/criar/', views.criar_cliente, name='criar_cliente'),
    path('api/clientes/editar/<int:id>/', views.editar_cliente, name='editar_cliente'),
    path('api/clientes/ajustar-pontos/<int:id>/', views.ajustar_pontos_cliente, name='ajustar_pontos_cliente'),
    path('api/clientes/excluir/<int:id>/', views.excluir_cliente, name='excluir_cliente'),
    path('api/clientes/excluir-multiplos/', views.excluir_multiplos_clientes, name='excluir_multiplos_clientes'),
    path('api/clientes/estatisticas/', views.estatisticas_clientes, name='estatisticas_clientes'),
    path('api/clientes/historico-pontos/<int:id>/', views.historico_pontos_cliente, name='historico_pontos_cliente'),
]