from django.urls import path
from . import views
from .api import receita_por_periodo

urlpatterns = [
    path('dashboard/', views.ver_dashboard, name='ver_dashboard'),
    path('api/dashboard/receita/', receita_por_periodo, name='api_receita'),
]
