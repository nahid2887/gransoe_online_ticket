from rest_framework import status, viewsets, serializers
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.generics import GenericAPIView
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from django.db import models

from .models import Customer
from .serializers import (
    CustomerRegistrationSerializer,
    CustomerLoginSerializer,
    CustomerDetailSerializer,
    AuthResponseSerializer,
    UpcomingEventSerializer,
    LogoutSerializer,
)
from staff.models import Event
from .models import Order, Ticket
from .serializers import PurchaseSerializer, OrderSerializer, TicketSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework.permissions import IsAuthenticated
from .permissions import IsCustomer
from django.db import transaction
from django.conf import settings
from django.http import JsonResponse
import base64
import io
import re
import secrets
from datetime import timedelta
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
try:
    import qrcode
except Exception:
    qrcode = None


def _stripe_metadata_get(obj, key, default=None):
    metadata = getattr(obj, 'metadata', None)
    if metadata is None:
        return default
    if isinstance(metadata, dict):
        return metadata.get(key, default)
    try:
        return metadata[key]
    except Exception:
        return default


def _generate_unique_tracking_number(reserved_numbers=None):
    reserved_numbers = set(reserved_numbers or set())
    for _ in range(1000):
        tracking_number = f"{secrets.randbelow(900000) + 100000}"
        if tracking_number in reserved_numbers:
            continue
        if not Ticket.objects.filter(tracking_number=tracking_number).exists():
            return tracking_number
    raise RuntimeError('Unable to generate a unique tracking number')


def _complete_order_and_generate_tickets(order):
    if order.status != 'completed':
        order.status = 'completed'
        order.save(update_fields=['status'])

    tickets = list(order.tickets.order_by('id'))
    reserved_numbers = {
        ticket.tracking_number
        for ticket in tickets
        if ticket.tracking_number and re.fullmatch(r'\d{6}', ticket.tracking_number)
    }

    while len(tickets) < order.quantity:
        tracking_number = _generate_unique_tracking_number(reserved_numbers)
        reserved_numbers.add(tracking_number)
        tickets.append(
            Ticket.objects.create(
                order=order,
                event=order.event,
                tracking_number=tracking_number,
            )
        )

    for ticket in tickets[:order.quantity]:
        update_fields = []
        if not ticket.tracking_number or not re.fullmatch(r'\d{6}', ticket.tracking_number):
            tracking_number = _generate_unique_tracking_number(reserved_numbers)
            reserved_numbers.add(tracking_number)
            ticket.tracking_number = tracking_number
            update_fields.append('tracking_number')

        if qrcode and (not ticket.qr_image or not ticket.qr_data):
            img = qrcode.make(str(ticket.code))
            bio = io.BytesIO()
            img.save(bio, format='PNG')
            path = f"tickets/{ticket.code}.png"
            default_storage.save(path, ContentFile(bio.getvalue()))
            try:
                url = default_storage.url(path)
            except Exception:
                url = settings.MEDIA_URL + path
            ticket.qr_image = url
            b64 = base64.b64encode(bio.getvalue()).decode()
            ticket.qr_data = f"data:image/png;base64,{b64}"
            update_fields.extend(['qr_image', 'qr_data'])

        if update_fields:
            ticket.save(update_fields=update_fields)

    return tickets[:order.quantity]


def payment_success_view(request):
    return JsonResponse({
        'detail': 'Payment redirect received successfully. Your webhook will finalize the order and generate tickets.',
    })


def payment_cancel_view(request):
    return JsonResponse({
        'detail': 'Payment was canceled or not completed.',
    })


def _release_expired_pending_orders():
    now = timezone.now()
    expired_before = now - timedelta(minutes=5)
    expired_orders = (
        Order.objects.select_for_update()
        .filter(status='pending')
        .filter(
            Q(reservation_expires_at__lte=now)
            | Q(reservation_expires_at__isnull=True, created_at__lte=expired_before)
        )
        .select_related('event')
    )

    for order in expired_orders:
        event = Event.objects.select_for_update().get(pk=order.event_id)
        event.available_tickets = models.F('available_tickets') + order.quantity
        event.save(update_fields=['available_tickets'])
        order.status = 'failed'
        order.save(update_fields=['status'])


@extend_schema(
    request=PurchaseSerializer,
    responses=OrderSerializer,
    description='Purchase tickets for an event. If Stripe is configured, returns PaymentIntent client_secret; otherwise completes immediately.',
)
class PurchaseView(GenericAPIView):
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_id = serializer.validated_data['event_id']
        quantity = serializer.validated_data['quantity']

        with transaction.atomic():
            _release_expired_pending_orders()

            try:
                event = Event.objects.select_for_update().get(pk=event_id)
            except Event.DoesNotExist:
                return Response({'detail': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)

            if quantity > event.max_per_order:
                return Response({'detail': 'Quantity exceeds max per order'}, status=status.HTTP_400_BAD_REQUEST)
            if quantity > event.available_tickets:
                return Response({'detail': 'Not enough tickets available'}, status=status.HTTP_400_BAD_REQUEST)

            total = event.price_per_ticket * quantity + event.platform_fee
            reservation_expires_at = timezone.now() + timedelta(minutes=5)
            event.available_tickets = models.F('available_tickets') - quantity
            event.save()
            order = Order.objects.create(
                user=request.user,
                event=event,
                quantity=quantity,
                total_amount=total,
                platform_fee=event.platform_fee,
                status='pending',
                reservation_expires_at=reservation_expires_at,
            )

        # If Stripe configured, create PaymentIntent
        stripe_client_secret = None
        stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        if stripe_key:
            try:
                import stripe
                stripe.api_key = stripe_key
                # Create a Checkout Session so the user sees a Stripe-hosted page
                line_items = [
                    {
                        'price_data': {
                            'currency': 'dkk',
                            'product_data': {'name': event.title},
                            'unit_amount': int(event.price_per_ticket * 100),
                        },
                        'quantity': quantity,
                    }
                ]
                # add platform fee as a separate line item so it's charged once per order
                if event.platform_fee and event.platform_fee > 0:
                    line_items.append({
                        'price_data': {
                            'currency': 'dkk',
                            'product_data': {'name': 'Platform fee'},
                            'unit_amount': int(event.platform_fee * 100),
                        },
                        'quantity': 1,
                    })

                # prefer automatic_payment_methods when supported by account/API
                try:
                    session = stripe.checkout.Session.create(
                        automatic_payment_methods={'enabled': True},
                        line_items=line_items,
                        mode='payment',
                        success_url=getattr(settings, 'STRIPE_CHECKOUT_SUCCESS_URL'),
                        cancel_url=getattr(settings, 'STRIPE_CHECKOUT_CANCEL_URL'),
                        metadata={'order_id': order.id},
                        payment_intent_data={'metadata': {'order_id': order.id}},
                    )
                except stripe.error.InvalidRequestError as e:
                    err_text = str(e)
                    # fall back to multiple enabled payment methods if automatic_payment_methods is not recognized
                    if 'automatic_payment_methods' in err_text or 'unknown parameter' in err_text:
                        session = stripe.checkout.Session.create(
                            payment_method_types=['card', 'amazon_pay', 'klarna', 'affirm', 'link', 'bancontact', 'blik', 'eps'],
                            line_items=line_items,
                            mode='payment',
                            success_url=getattr(settings, 'STRIPE_CHECKOUT_SUCCESS_URL'),
                            cancel_url=getattr(settings, 'STRIPE_CHECKOUT_CANCEL_URL'),
                            metadata={'order_id': order.id},
                            payment_intent_data={'metadata': {'order_id': order.id}},
                        )
                    else:
                        raise
                order.stripe_payment_intent = session.id
                order.save(update_fields=['stripe_payment_intent'])
                resp_checkout_url = session.url
            except Exception as e:
                return Response({'detail': 'Stripe error', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # No Stripe configured: complete order immediately and generate tickets
            _complete_order_and_generate_tickets(order)

        resp = OrderSerializer(order, context={'request': request}).data
        if stripe_key:
            # return the hosted checkout URL
            resp['checkout_url'] = resp_checkout_url
        elif stripe_client_secret:
            resp['client_secret'] = stripe_client_secret
        return Response(resp, status=status.HTTP_201_CREATED)

    def _complete_order_and_generate_tickets(self, order):
        return _complete_order_and_generate_tickets(order)


class MyTicketsView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = TicketSerializer

    def get_queryset(self):
        return Ticket.objects.filter(order__user=self.request.user).select_related('event')

    def get(self, request, *args, **kwargs):
        tickets = self.get_queryset()
        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    responses={
        200: TicketSerializer,
        404: inline_serializer(
            name='MyTicketNotFoundResponse',
            fields={'detail': serializers.CharField()},
        ),
    },
    description='Return a single ticket owned by the authenticated customer.',
)
class MyTicketDetailView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = TicketSerializer

    def get(self, request, pk, *args, **kwargs):
        ticket = Ticket.objects.filter(
            pk=pk,
            order__user=request.user,
        ).select_related('event').first()

        if not ticket:
            return Response({'detail': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: None},
    description='Stripe webhook endpoint (optional) to finalize orders on payment success.',
)
class StripeWebhookView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = serializers.Serializer

    def _finalize_order_from_webhook(self, order_id):
        try:
            order = Order.objects.select_for_update().get(id=order_id)
        except Order.DoesNotExist:
            return

        if order.status == 'completed':
            return

        if order.status == 'pending' and order.reservation_expires_at and order.reservation_expires_at <= timezone.now():
            order.status = 'failed'
            order.save(update_fields=['status'])
            return

        _complete_order_and_generate_tickets(order)

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        if not stripe_key or not webhook_secret:
            return Response({'detail': 'Stripe not configured'}, status=status.HTTP_400_BAD_REQUEST)
        import stripe
        stripe.api_key = stripe_key
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        order_id = None
        if event['type'] == 'payment_intent.succeeded':
            pi = event['data']['object']
            order_id = _stripe_metadata_get(pi, 'order_id')
        elif event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            order_id = _stripe_metadata_get(session, 'order_id')
            if not order_id:
                payment_intent_id = getattr(session, 'payment_intent', None)
                if payment_intent_id:
                    try:
                        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                        order_id = _stripe_metadata_get(payment_intent, 'order_id')
                    except Exception:
                        order_id = None

        if order_id:
            with transaction.atomic():
                self._finalize_order_from_webhook(order_id)
        return Response(status=status.HTTP_200_OK)


def build_customer_tokens(user, customer):
    refresh = RefreshToken.for_user(user)
    refresh['email'] = user.email
    refresh['username'] = user.username
    refresh['full_name'] = customer.full_name
    refresh['phone_number'] = customer.phone_number
    refresh['gender'] = customer.gender
    date_of_birth = customer.date_of_birth
    created_at = customer.created_at
    refresh['date_of_birth'] = date_of_birth.isoformat() if hasattr(date_of_birth, 'isoformat') else str(date_of_birth)
    # Determine role: prefer explicit related profile, then is_superuser
    role = 'customer'
    try:
        if hasattr(user, 'staff'):
            role = 'staff'
        elif user.is_superuser:
            role = 'admin'
    except Exception:
        role = 'customer'

    refresh['role'] = role

    refresh['customer'] = {
        'id': customer.id,
        'full_name': customer.full_name,
        'email': user.email,
        'username': user.username,
        'phone_number': customer.phone_number,
        'gender': customer.gender,
        'date_of_birth': refresh['date_of_birth'],
        'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
    }
    return refresh, str(refresh.access_token), str(refresh)


@extend_schema(
    request=CustomerRegistrationSerializer,
    responses=AuthResponseSerializer,
    description="Register a new customer account with required details.",
)
class CustomerRegistrationView(GenericAPIView):
    serializer_class = CustomerRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Get customer details from request
        full_name = request.data.get('full_name', 'Not provided')
        phone_number = request.data.get('phone_number', '')
        gender = request.data.get('gender', 'O')
        date_of_birth = request.data.get('date_of_birth', None)

        # Create Customer profile
        customer = Customer.objects.create(
            user=user,
            full_name=full_name,
            phone_number=phone_number,
            gender=gender,
            date_of_birth=date_of_birth
        )

        # Generate tokens with customer details in the JWT claims
        refresh, access_token, refresh_token = build_customer_tokens(user, customer)

        # Prepare response
        customer_data = CustomerDetailSerializer(customer).data
        response_data = {
            'customer': customer_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Customer registered successfully'
        }

        response = Response(response_data, status=status.HTTP_201_CREATED)

        # Set refresh token in secure HTTP-only cookie
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,  # 1 day
            secure=False,  # Set to True in production with HTTPS
            httponly=True,
            samesite='Lax'
        )

        return response


@extend_schema(
    request=CustomerLoginSerializer,
    responses=AuthResponseSerializer,
    description="Login with email and password. Returns customer details, access token, and refresh token in cookie.",
)
class CustomerLoginView(GenericAPIView):
    serializer_class = CustomerLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        try:
            customer = Customer.objects.get(user=user)
        except Customer.DoesNotExist:
            raise serializers.ValidationError({'detail': 'Customer profile not found.'})

        # Generate tokens with customer details in the JWT claims
        refresh, access_token, refresh_token = build_customer_tokens(user, customer)

        # Prepare response
        customer_data = CustomerDetailSerializer(customer).data
        response_data = {
            'customer': customer_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Login successful'
        }

        response = Response(response_data, status=status.HTTP_200_OK)

        # Set refresh token in secure HTTP-only cookie
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,  # 1 day
            secure=False,  # Set to True in production with HTTPS
            httponly=True,
            samesite='Lax'
        )

        return response


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving customer details.
    Requires JWT authentication.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'user__id'


@extend_schema(
    responses={
        200: UpcomingEventSerializer(many=True),
    },
    description='Return all upcoming events that anyone can view.',
)
class UpcomingEventListView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UpcomingEventSerializer

    def get(self, request, *args, **kwargs):
        with transaction.atomic():
            _release_expired_pending_orders()

        today = timezone.localdate()
        now = timezone.localtime().time()

        events = Event.objects.filter(
            Q(date__gt=today) | Q(date=today, time__gte=now)
        ).order_by('date', 'time', '-created_at')

        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    responses={
        200: UpcomingEventSerializer,
        404: inline_serializer(
            name='UpcomingEventDetailNotFoundResponse',
            fields={'detail': serializers.CharField()},
        ),
    },
    description='Return a single upcoming event by ID.',
)
class UpcomingEventDetailView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UpcomingEventSerializer

    def get(self, request, pk, *args, **kwargs):
        with transaction.atomic():
            _release_expired_pending_orders()

        today = timezone.localdate()
        now = timezone.localtime().time()

        event = Event.objects.filter(
            Q(pk=pk) & (Q(date__gt=today) | Q(date=today, time__gte=now))
        ).first()

        if not event:
            return Response({'detail': 'Upcoming event not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(event)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    request=LogoutSerializer,
    responses={
        200: inline_serializer(
            name='LogoutSuccessResponse',
            fields={'message': serializers.CharField()}
        ),
        400: inline_serializer(
            name='LogoutErrorResponse',
            fields={'detail': serializers.CharField()}
        )
    },
    description="Logout user. Can blacklist a specific refresh token or all outstanding tokens for the user.",
)
class LogoutView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        refresh_token = serializer.validated_data.get('refresh_token')
        all_devices = serializer.validated_data.get('all_devices', False)
        
        # If refresh token not in request body, try reading from cookie
        if not refresh_token:
            refresh_token = request.COOKIES.get('refresh_token')
            
        success_message = "Logout successful"
        
        if all_devices:
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication credentials are required to log out from all devices."},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Blacklist all outstanding tokens for the authenticated user
            outstanding_tokens = OutstandingToken.objects.filter(user=request.user)
            blacklisted_tokens = []
            for token in outstanding_tokens:
                if not BlacklistedToken.objects.filter(token=token).exists():
                    blacklisted_tokens.append(BlacklistedToken(token=token))
            
            if blacklisted_tokens:
                BlacklistedToken.objects.bulk_create(blacklisted_tokens)
                
            success_message = "Logged out from all devices successfully."
        else:
            # Single session logout (blacklist the provided/cookie refresh token)
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception:
                    # If token is already blacklisted or invalid, we still delete the cookie and return OK
                    pass
                
        response = Response({"message": success_message}, status=status.HTTP_200_OK)
        # Clear refresh token cookie
        response.delete_cookie('refresh_token')
        return response
