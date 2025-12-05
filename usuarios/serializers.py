from rest_framework import serializers
from .models import Categoria, Producto, Pedido, ItemPedido, Carrito, ItemCarrito
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role']
    
    def get_role(self, obj):
        if obj.is_superuser:
            return 'admin'
        if obj.is_staff:
            return 'staff'
        return 'cliente'

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'

class ProductoSerializer(serializers.ModelSerializer):
    categoria = serializers.StringRelatedField() 
    
    class Meta:
        model = Producto
        fields = '__all__'


class ItemPedidoSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer(read_only=True)
    
    class Meta:
        model = ItemPedido
        fields = ['producto', 'cantidad', 'precio_en_pedido','nombre_producto']

class PedidoSerializer(serializers.ModelSerializer):
    items = ItemPedidoSerializer(many=True, read_only=True)
    usuario = UserSerializer(read_only=True)
    
    class Meta:
        model = Pedido
        fields = ['id', 'usuario', 'total', 'estado', 'metodo_pago', 'direccion_entrega', 'fecha_creacion', 'items']


class ItemCarritoSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer(read_only=True)
    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(), source='producto', write_only=True
    )
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ItemCarrito
        fields = ['id', 'producto', 'producto_id', 'cantidad', 'subtotal']

    def get_subtotal(self, obj):
        return obj.producto.precio * obj.cantidad

class CarritoSerializer(serializers.ModelSerializer):
    items = ItemCarritoSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()
    
    class Meta:
        model = Carrito
        fields = ['id', 'usuario', 'items', 'creado_en', 'total']

    def get_total(self, obj):
        return sum(item.producto.precio * item.cantidad for item in obj.items.all())