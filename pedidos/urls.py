from django.urls import path
from . import views

urlpatterns = [
    path('pedidos/', views.ver_pedidos, name='ver_pedidos'),
    path('api/pedidos/', views.listar_pedidos, name='listar_pedidos'),
    path('api/pedidos/detalhes/<int:id>/', views.detalhes_pedido, name='detalhes_pedido'),
    path('api/pedidos/clientes/', views.listar_clientes, name='listar_clientes'),
    path('api/pedidos/artigos/', views.listar_artigos, name='listar_artigos'),
    path('api/pedidos/criar/', views.criar_pedido, name='criar_pedido'),
    path('api/pedidos/editar/<int:id>/', views.editar_pedido, name='editar_pedido'),
    path('api/pedidos/pagamento/<int:id>/', views.registrar_pagamento, name='registrar_pagamento'),
    path('api/pedidos/excluir/<int:id>/', views.excluir_pedido, name='excluir_pedido'),
    path('api/pedidos/atualizar-status/<int:id>/', views.atualizar_status_pedido, name='atualizar_status_pedido'),
    path('api/pedidos/recibo-imagem/<int:id>/', views.imprimir_recibo_imagem, name='imprimir_recibo_imagem'),

    # Rotas de SMS
    path('api/pedidos/enviar-sms/<int:pedido_id>/', views.enviar_sms_pedido_pronto, name='enviar_sms_pedido_pronto'),
    path('api/pedidos/enviar-sms-cobranca/<int:pedido_id>/', views.enviar_sms_cobranca, name='enviar_sms_cobranca'),
    path('api/pedidos/enviar-sms-personalizado/', views.enviar_sms_personalizado, name='enviar_sms_personalizado'),
    path('api/pedidos/enviar-sms-teste/', views.enviar_sms_teste, name='enviar_sms_teste'),
]