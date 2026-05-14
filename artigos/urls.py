from django.urls import path
from . import views

urlpatterns = [
    # Página principal de artigos
    path('artigos/', views.ver_artigo, name='ver_artigo'),

    # APIs para artigos
    path('api/artigos/', views.listar_artigos, name='listar_artigos'),
    path('api/artigos/criar/', views.criar_artigo, name='criar_artigo'),
    path('api/artigos/editar/<int:id>/', views.editar_artigo, name='editar_artigo'),
    path('api/artigos/toggle/<int:id>/', views.alternar_status_artigo, name='alternar_status_artigo'),
    path('api/artigos/excluir/<int:id>/', views.excluir_artigo, name='excluir_artigo'),
    path('api/artigos/excluir-multiplos/', views.excluir_multiplos_artigos, name='excluir_multiplos_artigos'),
]