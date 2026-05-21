from django.urls import path
from . import views

urlpatterns = [
    path('relatorios/', views.ver_relatorios, name='ver_relatorios'),
    path('api/relatorios/dados/', views.dados_relatorios, name='dados_relatorios'),
]