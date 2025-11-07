# En usuarios/urls.py (archivo nuevo)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Creamos un router para los ViewSets
router = DefaultRouter()
router.register(r'productos', views.ProductoViewSet, basename='producto')
router.register(r'carrito', views.CarritoViewSet, basename='carrito')
router.register(r'pedidos', views.PedidoViewSet, basename='pedido')

# Definimos las URLs de la API
urlpatterns = [
    # --- Autenticación ---
    # (ej: POST /api/auth/register)
    path('auth/register', views.register_view, name='register'),
    path('auth/login', views.login_view, name='login'),
    path('auth/logout', views.logout_view, name='logout'),
    path('auth/me', views.me_view, name='me'), # Para ver quién soy
    
    # --- Staff ---
    # (ej: PATCH /api/productos/5/available)
    path('productos/<int:pk>/available', views.toggle_product_availability, name='toggle-product'),

    # --- URLs de los ViewSets (Productos, Carrito, Pedidos) ---
    # Esto crea automáticamente las URLs para:
    # /api/productos/
    # /api/productos/{id}/
    # /api/carrito/ver_carrito/
    # /api/carrito/agregar_item/
    # /api/pedidos/
    # ...etc.
    path('', include(router.urls)),
]