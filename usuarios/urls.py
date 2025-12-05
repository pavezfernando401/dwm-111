# En restaurante/usuarios/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views # Importa tu archivo views.py

# 1. Creamos un "router" para los ViewSets
# Esto crea automáticamente las URLs para Producto, Carrito y Pedido
# (ej: /productos/, /productos/{id}/, /carrito/agregar_item/, etc.)
router = DefaultRouter()
router.register(r'productos', views.ProductoViewSet, basename='producto')
router.register(r'carrito', views.CarritoViewSet, basename='carrito')
router.register(r'pedidos', views.PedidoViewSet, basename='pedidos')

# 2. Creamos las URLs para las vistas de función (las que no son ViewSets)
urlpatterns = [
    # --- Autenticación ---
    path('auth/register/', views.register_view, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me_view, name='me'),
    path('auth/password-reset/', views.password_reset_request, name='password-reset'),
    path('auth/password-reset-confirm/', views.password_reset_confirm, name='password-reset-confirm'),
    path('productos/<int:pk>/toggle_availability/', views.toggle_product_availability, name='toggle-availability'),
    path('', include(router.urls)),
    path('reports/stats/', views.dashboard_stats, name='dashboard-stats'),
    path('auth/profile/update/', views.update_profile, name='profile-update'),
    path('auth/change-password/', views.change_password, name='change-password'),
]