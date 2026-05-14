from django.urls import path
from . import views

urlpatterns = [
    path('lavandarias/', views.ver_lavandarias, name='ver_lavandarias'),
    path('api/lavandarias/', views.listar_lavandarias, name='listar_lavandarias'),
    path('api/lavandarias/criar/', views.criar_lavandaria, name='criar_lavandaria'),
    path('api/lavandarias/editar/<int:id>/', views.editar_lavandaria, name='editar_lavandaria'),
    path('api/lavandarias/excluir/<int:id>/', views.excluir_lavandaria, name='excluir_lavandaria'),
    path('api/lavandarias/estatisticas/', views.estatisticas_lavandarias, name='estatisticas_lavandarias'),
    path('api/lavandarias/detalhes/<int:id>/', views.detalhes_lavandaria, name='detalhes_lavandaria'),
]