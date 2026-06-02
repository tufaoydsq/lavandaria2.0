from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),


    path('', include('login.urls')),  # Isso fará o login ser a página inicial

    path('', include('core.urls')),


    path('', include('dashboard.urls')),
    path('', include('artigos.urls')),
    path('', include('cliente.urls')),
    path('', include('lavandarias.urls')),
    path('', include('funcionarios.urls')),
    path('', include('user.urls')),
    path('', include('pedidos.urls')),
    path('', include('relatorios.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)