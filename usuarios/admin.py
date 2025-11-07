from django.contrib import admin
from .models import Categoria, Producto, Pedido, ItemPedido, Carrito, ItemCarrito

# Registra los modelos para que aparezcan en el panel de admin
admin.site.register(Categoria)
admin.site.register(Producto)
admin.site.register(Pedido)
admin.site.register(ItemPedido)
admin.site.register(Carrito)
admin.site.register(ItemCarrito)