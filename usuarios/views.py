# En usuarios/views.py
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets, status, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action, authentication_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.authentication import SessionAuthentication

from .models import Producto, Categoria, Pedido, ItemPedido, Carrito, ItemCarrito
from .serializers import (
    ProductoSerializer, CategoriaSerializer, PedidoSerializer, 
    UserSerializer, CarritoSerializer, ItemCarritoSerializer
)

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Esta clase es idéntica a SessionAuthentication pero
    desactiva la validación CSRF de DRF.
    """
    def enforce_csrf(self, request):
        return  # No hacer nada (se salta la validación CSRF)

# --- Vistas de Autenticación ---

@api_view(['POST'])
@permission_classes([AllowAny]) # Cualquiera puede intentar registrarse
def register_view(request):
    """
    Crea un nuevo usuario.
    """
    data = request.data
    try:
        # Crea el usuario
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            first_name=data.get('nombre', '')
        )
        # Opcional: Crear su carrito de compras
        Carrito.objects.create(usuario=user)
        
        return Response({'message': 'Usuario registrado exitosamente'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt  # <-- Asegúrate que esto siga aquí
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """
    Autentica a un usuario y crea una sesión.
    """
    email = request.data.get('email')
    password = request.data.get('password')
    
    # --- LÓGICA DE LOGIN CORREGIDA ---
    try:
        # 1. Primero, encontramos al usuario por su email
        user_obj = User.objects.get(email=email)
        
        # 2. Ahora, autenticamos usando el USERNAME real de ese usuario
        user = authenticate(request, username=user_obj.username, password=password)
        
    except User.DoesNotExist:
        user = None # Si el email no existe, user es None
    # --- FIN DE LA LÓGICA ---
    
    if user:
        login(request, user) # Inicia la sesión
        serializer = UserSerializer(user)
        # El frontend espera una clave 'user', pero aquí no importa
        # porque el frontend llama a /api/auth/me inmediatamente.
        return Response(serializer.data)
    else:
        # Si user es None (ya sea por email o pass incorrecta), falla.
        return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated]) # Solo usuarios logueados pueden cerrar sesión
def logout_view(request):
    """
    Cierra la sesión del usuario actual.
    """
    logout(request)
    return Response({'message': 'Sesión cerrada exitosamente'})


@api_view(['GET'])
@permission_classes([IsAuthenticated]) # Solo usuarios logueados pueden ver su perfil
def me_view(request):
    """
    Devuelve la información del usuario actualmente logueado.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

# --- Vistas de Productos (Catálogo) ---

class ProductoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API para ver productos.
    Permite filtrar por categoria y buscar por nombre (q).
    """
    permission_classes = [AllowAny] # Todos pueden ver el catálogo
    serializer_class = ProductoSerializer

    def get_queryset(self):
        queryset = Producto.objects.all().order_by('nombre')
        
        # Filtro por categoría (ej: /api/productos?category=Shawarma)
        categoria_nombre = self.request.query_params.get('category')
        if categoria_nombre:
            queryset = queryset.filter(categoria__nombre=categoria_nombre)
            
        # Filtro de búsqueda (ej: /api/productos?q=Pollo)
        search_query = self.request.query_params.get('q')
        if search_query:
            # 'icontains' es "case-insensitive" (ignora mayúsculas/minúsculas)
            queryset = queryset.filter(nombre__icontains=search_query)

        # Solo disponibles (para clientes)
        # El frontend de staff no envía este param, el de cliente sí.
        if self.request.query_params.get('onlyAvailable') == '1':
             queryset = queryset.filter(disponible=True)

        return queryset
@csrf_exempt
@api_view(['PATCH'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAdminUser]) # Asumimos que solo Admin/Staff pueden cambiar esto
def toggle_product_availability(request, pk):
    """
    Vista para que el staff marque un producto como disponible o agotado.
    Espera un body JSON como: { "available": 0 } o { "available": 1 }
    """
    producto = get_object_or_404(Producto, pk=pk)
    
    # 'available' debe ser 0 o 1 (booleano)
    is_available = request.data.get('available') 
    
    if is_available is None:
        return Response({'error': 'Falta el campo "available" (0 o 1)'}, status=status.HTTP_400_BAD_REQUEST)

    producto.disponible = bool(is_available)
    producto.save()
    
    serializer = ProductoSerializer(producto)
    return Response(serializer.data, status=status.HTTP_200_OK)


# --- Vistas de Carrito ---
class CarritoViewSet(viewsets.ViewSet):
    """
    API para el Carrito de Compras.
    Requiere que el usuario esté autenticado.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_cart(self, request):
        """Función helper para obtener o crear un carrito para el usuario"""
        # .get_or_create() devuelve (objeto, booleano_fue_creado)
        carrito, created = Carrito.objects.get_or_create(usuario=request.user)
        return carrito

    @action(detail=False, methods=['get'])
    def ver_carrito(self, request):
        """
        GET /api/carrito/ver_carrito
        Devuelve el carrito del usuario.
        """
        carrito = self.get_cart(request)
        serializer = CarritoSerializer(carrito)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def agregar_item(self, request):
        """
        POST /api/carrito/agregar_item
        Agrega un producto al carrito.
        Body: { "producto_id": X, "cantidad": Y }
        """
        carrito = self.get_cart(request)
        producto_id = request.data.get('producto_id')
        cantidad = int(request.data.get('cantidad', 1))
        
        if not producto_id:
            return Response({'error': 'Falta producto_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        producto = get_object_or_404(Producto, pk=producto_id)
        
        if not producto.disponible:
            return Response({'error': 'Producto no disponible'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Buscar si el item ya existe en el carrito
        item, created = ItemCarrito.objects.get_or_create(
            carrito=carrito, 
            producto=producto
        )
        
        if created:
            item.cantidad = cantidad
        else:
            # Si ya existe, suma la cantidad
            item.cantidad += cantidad
        
        item.save()
        
        serializer = CarritoSerializer(carrito)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def actualizar_item(self, request, pk=None):
        """
        PATCH /api/carrito/{item_id}/actualizar_item
        Actualiza la cantidad de un item.
        Body: { "cantidad": Y }
        """
        carrito = self.get_cart(request)
        item = get_object_or_404(ItemCarrito, pk=pk, carrito=carrito)
        
        cantidad = int(request.data.get('cantidad', 1))
        
        if cantidad <= 0:
            # Si la cantidad es 0 o menos, borra el item
            item.delete()
        else:
            item.cantidad = cantidad
            item.save()
            
        serializer = CarritoSerializer(carrito)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'])
    def eliminar_item(self, request, pk=None):
        """
        DELETE /api/carrito/{item_id}/eliminar_item
        Elimina un item del carrito.
        """
        carrito = self.get_cart(request)
        item = get_object_or_404(ItemCarrito, pk=pk, carrito=carrito)
        item.delete()
        
        serializer = CarritoSerializer(carrito)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def limpiar_carrito(self, request):
        """
        POST /api/carrito/limpiar_carrito
        Vacía todos los items del carrito.
        """
        carrito = self.get_cart(request)
        carrito.items.all().delete()
        
        serializer = CarritoSerializer(carrito)
        return Response(serializer.data)


# --- Vistas de Pedidos ---

class PedidoViewSet(viewsets.ViewSet):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    # --- FUNCIÓN DE AYUDA (para buscar Pedidos por ID) ---
    def get_object(self, pk=None):
        try:    
            return Pedido.objects.get(pk=pk)
        except Pedido.DoesNotExist:
            raise Http404

    # --- API para /api/pedidos/ (GET, para clientes) ---
    def list(self, request):
        """
        Devuelve la lista de pedidos del usuario logueado.
        """
        pedidos = Pedido.objects.filter(usuario=request.user).order_by('-fecha_creacion')
        serializer = PedidoSerializer(pedidos, many=True)
        return Response(serializer.data)

    # --- API para /api/pedidos/ (POST, para clientes) ---
    def create(self, request):
        """
        Crea un nuevo pedido a partir del carrito del usuario.
        """
        carrito = get_object_or_404(Carrito, usuario=request.user)
        items_carrito = carrito.items.all()
        
        if not items_carrito:
            return Response({'error': 'Tu carrito está vacío'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Usamos una transacción para asegurar que si algo falla, no se cree el pedido
        try:
            with transaction.atomic():
                total = sum(int(item.producto.precio) * int(item.cantidad) for item in items_carrito)
                metodo_pago = request.data.get('metodo_pago', 'TARJETA') # Leemos el método de pago
                
                # --- ¡NUEVA LÓGICA DE ESTADO AUTOMÁTICO! ---
                # Tarjeta y Efectivo (pago en entrega) se aprueban al instante.
                # Transferencia queda Pendiente para que la Caja la revise.
                if metodo_pago in ['TARJETA', 'EFECTIVO']:
                    estado_inicial = 'EN PREPARACION'
                else: # (metodo_pago == 'TRANSFERENCIA')
                    estado_inicial = 'PENDIENTE'
                # 2. Crear el Pedido
                pedido = Pedido.objects.create(
                    usuario=request.user,
                    total=total,
                    metodo_pago=request.data.get('metodo_pago', 'TARJETA'),
                    direccion_entrega=request.data.get('direccion_entrega', 'Dirección de prueba')
                )
                
                # 3. Mover items del carrito a ItemPedido
                for item_c in items_carrito:
                    ItemPedido.objects.create(
                        pedido=pedido,
                        producto=item_c.producto,
                        cantidad=item_c.cantidad,
                        precio_en_pedido=int(item_c.producto.precio)
                    )
                
                # 4. Limpiar el carrito
                carrito.items.all().delete()
                
                # 5. Devolver el pedido creado
                serializer = PedidoSerializer(pedido)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'Error al crear el pedido: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- API para /api/pedidos/active_orders/ (GET, para Caja) ---
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def active_orders(self, request):
        """
        Devuelve una lista de pedidos activos (Pendientes o En Preparación)
        para la vista de Caja.
        """
        pedidos = Pedido.objects.filter(
            estado__in=['PENDIENTE', 'EN PREPARACION']
        ).order_by('fecha_creacion')
        
        serializer = PedidoSerializer(pedidos, many=True)
        return Response(serializer.data)

    # --- API PARA /api/pedidos/dispatch_list/ (GET, para Despacho) ---
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def dispatch_list(self, request):
        """
        Devuelve pedidos 'En Preparación' y 'En Camino' para Despacho.
        """
        pedidos = Pedido.objects.filter(
            estado__in=['EN PREPARACION', 'EN CAMINO']
        ).order_by('fecha_creacion')
        
        serializer = PedidoSerializer(pedidos, many=True)
        return Response(serializer.data)

    # --- API PARA /api/pedidos/<id>/update_status/ (PATCH, para Staff) ---
    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """
        Permite al staff actualizar el estado de un pedido.
        """
        pedido = self.get_object(pk=pk)
        new_status = request.data.get('estado')

        if not new_status:
            return Response({'error': 'Falta el campo "estado"'}, status=status.HTTP_400_BAD_REQUEST)

        valid_states = [choice[0] for choice in Pedido.ESTADO_CHOICES]
        if new_status not in valid_states:
            return Response({'error': 'Estado no válido'}, status=status.HTTP_400_BAD_REQUEST)

        pedido.estado = new_status
        pedido.save()
        
        serializer = PedidoSerializer(pedido)
        return Response(serializer.data)