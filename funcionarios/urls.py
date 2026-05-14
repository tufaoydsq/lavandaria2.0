from  django.urls import path
from . import views

urlpatterns = [
    path('funcionarios/', views.ver_funcionarios, name='ver_funcionarios'),
]