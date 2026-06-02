from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('do-login/', views.do_login, name='do_login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/password-reset/', views.password_reset_request, name='password_reset'),
]