# En usuarios/models.py

from django.db import models
from django.contrib.auth.models import User # Importamos el modelo User de Django
from decimal import Decimal

# Modelo para las Categorías de Productos
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.nombre

# Modelo para los Productos
class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.IntegerField()
    categoria = models.ForeignKey(Categoria, related_name='productos', on_delete=models.SET_NULL, null=True)
    imagen = models.CharField(max_length=500, blank=True, null=True) # Usamos CharField para la URL de la imagen
    disponible = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False)
    
    def __str__(self):
        return self.nombre

# Modelo para los Pedidos
class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN PREPARACION', 'En preparación'),
        ('EN CAMINO', 'En camino'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    PAGO_CHOICES = [
        ('TARJETA', 'Tarjeta'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('EFECTIVO', 'Efectivo'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pedidos')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    metodo_pago = models.CharField(max_length=20, choices=PAGO_CHOICES)
    direccion_entrega = models.CharField(max_length=255)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'Pedido #{self.id} - {self.usuario.username}'

# Modelo para los Items de un Pedido (los productos dentro del carrito)
class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True) 
    cantidad = models.IntegerField()
    precio_en_pedido = models.IntegerField()
    nombre_producto = models.CharField(max_length=200, blank=True) 

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.nombre_producto = self.producto.nombre
        super().save(*args, **kwargs)

    def __str__(self):
        nombre = self.nombre_producto if self.nombre_producto else (self.producto.nombre if self.producto else "Producto eliminado")
        return f'{self.cantidad}x {nombre} en Pedido #{self.pedido.id}'
    
    # Modelo para el Carrito de Compras
class Carrito(models.Model):
    # Usamos OneToOneField para que cada usuario tenga solo UN carrito
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='carrito')
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Carrito de {self.usuario.username}'

# Modelo para los Items en el Carrito
class ItemCarrito(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        # Asegura que no haya dos entradas para el mismo producto en el mismo carrito
        unique_together = ('carrito', 'producto') 

    def __str__(self):
        return f'{self.cantidad}x {self.producto.nombre}'