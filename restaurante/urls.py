# En restaurante/urls.py

from django.contrib import admin
from django.urls import path, include  # <-- Asegúrate de importar 'include'

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- NUEVA LÍNEA ---
    # Conecta todas las URLs de tu app 'usuarios' bajo el prefijo 'api/'
    path('api/', include('usuarios.urls')), 
]