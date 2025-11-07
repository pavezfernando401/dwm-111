# En usuarios/serializers.py

from rest_framework import serializers
from .models import Categoria, Producto, Pedido, ItemPedido, Carrito, ItemCarrito
from django.contrib.auth.models import User

# Serializer para el modelo de Usuario
class UserSerializer(serializers.ModelSerializer):
    # Campo "role" personalizado
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role'] # <-- 'role' añadido
    
    def get_role(self, obj):
        # Asigna un rol basado en los permisos de Django
        if obj.is_superuser:
            return 'admin'
        if obj.is_staff:
            return 'cajero' # Asume que staff = cajero
        return 'cliente'

# Serializer para Categoría
class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__' # Incluye todos los campos

# Serializer para Producto (Básico)
class ProductoSerializer(serializers.ModelSerializer):
    # para que en vez de mostrar el ID de la categoria, muestre el nombre
    categoria = serializers.StringRelatedField() 
    
    class Meta:
        model = Producto
        fields = '__all__'

# --- Serializers para Pedidos ---

# Serializer para ItemPedido (usado DENTRO de un pedido)
class ItemPedidoSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer(read_only=True) # Muestra info completa del producto
    
    class Meta:
        model = ItemPedido
        fields = ['producto', 'cantidad', 'precio_en_pedido']

# Serializer para ver un Pedido (con todos sus items)
class PedidoSerializer(serializers.ModelSerializer):
    items = ItemPedidoSerializer(many=True, read_only=True) # Anida los items del pedido
    usuario = UserSerializer(read_only=True) # Muestra info del usuario
    
    class Meta:
        model = Pedido
        fields = ['id', 'usuario', 'total', 'estado', 'metodo_pago', 'direccion_entrega', 'fecha_creacion', 'items']

# --- Serializers para Carrito ---

class ItemCarritoSerializer(serializers.ModelSerializer):
    # Usamos un serializer de producto anidado para MOSTRAR info
    producto = ProductoSerializer(read_only=True)
    # Usamos un ID simple para CREAR/ACTUALIZAR
    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(), source='producto', write_only=True
    )
    # También calculamos el subtotal por item
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ItemCarrito
        fields = ['id', 'producto', 'producto_id', 'cantidad', 'subtotal']

    def get_subtotal(self, obj):
        return obj.producto.precio * obj.cantidad

class CarritoSerializer(serializers.ModelSerializer):
    items = ItemCarritoSerializer(many=True, read_only=True)
    # Calculamos el total del carrito
    total = serializers.SerializerMethodField()
    
    class Meta:
        model = Carrito
        fields = ['id', 'usuario', 'items', 'creado_en', 'total']

    def get_total(self, obj):
        # Suma los subtotales de todos los items
        return sum(item.producto.precio * item.cantidad for item in obj.items.all())