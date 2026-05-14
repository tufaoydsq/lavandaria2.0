from django.urls import path
from . import views
from .api import receita_por_periodo

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/dashboard/receita/', receita_por_periodo, name='api_receita'),
]
