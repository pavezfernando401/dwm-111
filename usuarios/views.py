from django.db.models import Sum, Count
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.utils.http import urlsafe_base64_decode

from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

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
        return

@api_view(['POST'])
@permission_classes([AllowAny]) 
def register_view(request):
    """
    Crea un nuevo usuario.
    """
    data = request.data
    try:
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            first_name=data.get('nombre', '')
        )
        Carrito.objects.create(usuario=user)
        
        return Response({'message': 'Usuario registrado exitosamente'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """
    Autentica a un usuario y crea una sesión.
    """
    email = request.data.get('email')
    password = request.data.get('password')
    
    try:
        user_obj = User.objects.get(email=email)
        
        user = authenticate(request, username=user_obj.username, password=password)
        
    except User.DoesNotExist:
        user = None 

    
    if user:
        login(request, user)
        serializer = UserSerializer(user)
        return Response(serializer.data)
    else:
        return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated]) 
def logout_view(request):
    """
    Cierra la sesión del usuario actual.
    """
    logout(request)
    return Response({'message': 'Sesión cerrada exitosamente'})


@api_view(['GET'])
@permission_classes([IsAuthenticated]) 
def me_view(request):
    """
    Devuelve la información del usuario actualmente logueado.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

class ProductoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API para ver productos.
    Permite filtrar por categoria y buscar por nombre (q).
    """
    permission_classes = [AllowAny] 
    serializer_class = ProductoSerializer

    def get_queryset(self):
        queryset = Producto.objects.all().order_by('nombre')
        categoria_nombre = self.request.query_params.get('category')
        if categoria_nombre:
            queryset = queryset.filter(categoria__nombre=categoria_nombre)
            
        search_query = self.request.query_params.get('q')
        if search_query:
            queryset = queryset.filter(nombre__icontains=search_query)

        if self.request.query_params.get('onlyAvailable') == '1':
             queryset = queryset.filter(disponible=True)

        return queryset
@csrf_exempt
@api_view(['PATCH'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAdminUser]) 
def toggle_product_availability(request, pk):
    """
    Vista para que el staff marque un producto como disponible o agotado.
    Espera un body JSON como: { "available": 0 } o { "available": 1 }
    """
    producto = get_object_or_404(Producto, pk=pk)
    
    is_available = request.data.get('available') 
    
    if is_available is None:
        return Response({'error': 'Falta el campo "available" (0 o 1)'}, status=status.HTTP_400_BAD_REQUEST)

    producto.disponible = bool(is_available)
    producto.save()
    
    serializer = ProductoSerializer(producto)
    return Response(serializer.data, status=status.HTTP_200_OK)


class CarritoViewSet(viewsets.ViewSet):
    """
    API para el Carrito de Compras.
    Requiere que el usuario esté autenticado.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_cart(self, request):
        """Función helper para obtener o crear un carrito para el usuario"""
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
            
        item, created = ItemCarrito.objects.get_or_create(
            carrito=carrito, 
            producto=producto
        )
        
        if created:
            item.cantidad = cantidad
        else:
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


class PedidoViewSet(viewsets.ViewSet):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, pk=None):
        try:    
            return Pedido.objects.get(pk=pk)
        except Pedido.DoesNotExist:
            raise Http404

    def list(self, request):
        """
        Devuelve la lista de pedidos del usuario logueado.
        """
        pedidos = Pedido.objects.filter(usuario=request.user).order_by('-fecha_creacion')
        serializer = PedidoSerializer(pedidos, many=True)
        return Response(serializer.data)

    def create(self, request):
        """
        Crea un nuevo pedido a partir del carrito del usuario.
        """
        carrito = get_object_or_404(Carrito, usuario=request.user)
        items_carrito = carrito.items.all()
        
        if not items_carrito:
            return Response({'error': 'Tu carrito está vacío'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            with transaction.atomic():
                total = sum(int(item.producto.precio) * int(item.cantidad) for item in items_carrito)
                metodo_pago = request.data.get('metodo_pago', 'TARJETA')
                
                if metodo_pago in ['TARJETA', 'EFECTIVO']:
                    estado_inicial = 'EN PREPARACION'
                else:
                    estado_inicial = 'PENDIENTE'
                pedido = Pedido.objects.create(
                    usuario=request.user,
                    total=total,
                    metodo_pago=request.data.get('metodo_pago', 'TARJETA'),
                    direccion_entrega=request.data.get('direccion_entrega', 'Dirección de prueba')
                )
                
                for item_c in items_carrito:
                    ItemPedido.objects.create(
                        pedido=pedido,
                        producto=item_c.producto,
                        cantidad=item_c.cantidad,
                        precio_en_pedido=int(item_c.producto.precio)
                    )
                
                carrito.items.all().delete()
                

                serializer = PedidoSerializer(pedido)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'Error al crear el pedido: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    

@csrf_exempt
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def password_reset_request(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email requerido'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'message': 'Si el email existe, se envió un correo.'})

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    reset_link = f"http://127.0.0.1:5500/restaurante/usuarios/Templates/reset-confirm.html?uid={uid}&token={token}"

    subject = 'Recuperar Contraseña - Al Sahara'
    message = f"""Hola {user.first_name},

Recibimos una solicitud para restablecer tu contraseña.
Haz clic en el siguiente enlace para crear una nueva:

{reset_link}

Si no fuiste tú, ignora este mensaje.
"""

    try:
        send_mail(
            subject, 
            message, 
            settings.EMAIL_HOST_USER, 
            [email], 
            fail_silently=False
        )
        return Response({'message': 'Correo de recuperación enviado.'})
    except Exception as e:
        return Response({'error': 'Error enviando correo.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    uidb64 = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')

    if not uidb64 or not token or not new_password:
        return Response({'error': 'Faltan datos.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_bytes(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response({'error': 'Enlace inválido.'}, status=status.HTTP_400_BAD_REQUEST)

    if default_token_generator.check_token(user, token):
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Contraseña restablecida con éxito.'})
    else:
        return Response({'error': 'El enlace ha expirado o es inválido.'}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAdminUser])
def dashboard_stats(request):
    """
    Devuelve estadísticas filtradas por fecha.
    """
    pedidos_validos = Pedido.objects.exclude(estado='CANCELADO')
    
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')

    if start_date:
        pedidos_validos = pedidos_validos.filter(fecha_creacion__date__gte=start_date)
    if end_date:
        pedidos_validos = pedidos_validos.filter(fecha_creacion__date__lte=end_date)


    total_ventas = pedidos_validos.aggregate(Sum('total'))['total__sum'] or 0
    total_pedidos = pedidos_validos.count()
    ticket_promedio = total_ventas / total_pedidos if total_pedidos > 0 else 0

    por_estado = pedidos_validos.values('estado').annotate(cantidad=Count('id'))
    por_metodo = pedidos_validos.values('metodo_pago').annotate(cantidad=Count('id'))

    items_query = ItemPedido.objects.filter(pedido__in=pedidos_validos)
    
    top_productos = items_query.values('nombre_producto') \
        .annotate(total_vendido=Sum('cantidad')) \
        .order_by('-total_vendido')[:5]

    data = {
        'resumen': {
            'total_ventas': total_ventas,
            'cantidad_pedidos': total_pedidos,
            'ticket_promedio': round(ticket_promedio)
        },
        'graficos': {
            'estados': list(por_estado),
            'top_productos': list(top_productos),
            'metodos_pago': list(por_metodo)
        }
    }
    
    return Response(data)

@api_view(['PATCH'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    user.first_name = request.data.get('first_name', user.first_name)
    user.email = request.data.get('email', user.email)
    user.save()
    
    return Response({'message': 'Perfil actualizado correctamente'})

@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old_pass = request.data.get('old_password')
    new_pass = request.data.get('new_password')
    
    if not user.check_password(old_pass):
        return Response({'error': 'La contraseña actual es incorrecta'}, status=status.HTTP_400_BAD_REQUEST)
        
    user.set_password(new_pass)
    user.save()
    
    login(request, user)
    
    return Response({'message': 'Contraseña actualizada exitosamente'})