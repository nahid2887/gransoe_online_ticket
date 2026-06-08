from rest_framework import status, viewsets, serializers, mixins ,generics
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import GenericAPIView ,ListAPIView
from django.contrib.auth.models import User
from django.db.models import Q, Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User
from django.core.mail import send_mail
from .models import Staff 
from .models import PasswordResetOTP
from django.utils import timezone
import random
from .models import Event , Banner , Singer , AboutUs , PrivecyPolicy , TremsAndCondition
from .serializers import (
    StaffRegistrationSerializer,
    StaffLoginSerializer,
    StaffDetailSerializer,
    StaffAuthResponseSerializer,
    SuperuserLoginSerializer,
    SuperuserAuthResponseSerializer,
    SuperuserDetailSerializer,
    SuperuserProfileSerializer,
    SuperuserProfileResponseSerializer,
    SuperuserPasswordChangeSerializer,
    SuperuserPasswordChangeResponseSerializer,
    SuperuserDashboardResponseSerializer,
    StaffUpdateResponseSerializer,
    StaffDeleteResponseSerializer,
    OwnProfileResponseSerializer,
    OrderSerializer,
    BannerSerializer,
    SingerSerializer ,
    AboutUsSerializer,
    PrivecyPolicySerializer,
    TremsAndConditionSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer
)
from .serializers import EventSerializer
from staff.serializers import StaffTicketVerifySerializer
from customer.serializers import TicketSerializer
from customer.models import Ticket, Order, Customer
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission


class IsSuperUserForWrite(BasePermission):
    def has_permission(self, request, view):
        # allow safe methods for anyone, but require superuser for create/update/delete
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
        return True


class IsStaffUser(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_superuser or hasattr(user, 'staff'))


class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


@extend_schema_view(
    list=extend_schema(
        description='List all events',
        responses=EventSerializer(many=True)
    ),
    retrieve=extend_schema(
        description='Retrieve a single event by ID',
        responses=EventSerializer
    ),
    create=extend_schema(
        description='Create a new event (superuser only)',
        request=EventSerializer,
        responses=EventSerializer
    ),
    update=extend_schema(
        description='Update an event (superuser only)',
        request=EventSerializer,
        responses=EventSerializer
    ),
    partial_update=extend_schema(
        description='Partially update an event (superuser only)',
        request=EventSerializer,
        responses=EventSerializer
    ),
    destroy=extend_schema(
        description='Delete an event (superuser only)',
        responses={204: None}
    )
)
@extend_schema(tags=['Staff Events'])
class EventViewSet(viewsets.ModelViewSet):
    """Event endpoints: create/patch restricted to superusers."""
    serializer_class = EventSerializer
    permission_classes = [IsSuperUserForWrite]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return Event.objects.annotate(tickets_sold=Count('tickets', distinct=True)).order_by('-created_at')

    def _error_response(self, detail, *, errors=None, error=None, status_code=status.HTTP_400_BAD_REQUEST):
        payload = {'detail': detail}
        if errors is not None:
            payload['errors'] = errors
        if error is not None:
            payload['error'] = error
        return Response(payload, status=status_code)

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except serializers.ValidationError as exc:
            return self._error_response(
                'Unable to list events.',
                errors=exc.detail,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return self._error_response(
                'An unexpected error occurred while listing events.',
                error=str(exc),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except serializers.ValidationError as exc:
            return self._error_response(
                'Unable to create event.',
                errors=exc.detail,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return self._error_response(
                'An unexpected error occurred while creating the event.',
                error=str(exc),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    list=extend_schema(
        description='List upcoming events for staff users.',
        responses=EventSerializer(many=True),
    ),
    retrieve=extend_schema(
        description='Retrieve a single upcoming event by ID for staff users.',
        responses=EventSerializer,
    ),
)
@extend_schema(tags=['Staff Upcoming Events'])
class StaffUpcomingEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        with transaction.atomic():
            now = timezone.localtime()
            today = timezone.localdate()
            return (
                Event.objects.filter(
                    Q(date__gt=today) | Q(date=today, time__gte=now.time())
                )
                .order_by('date', 'time', '-created_at')
            )


@extend_schema(
    request=StaffTicketVerifySerializer,
    responses={200: TicketSerializer},
    description='Verify a ticket for a given event by `tracking_number` or `qr_data`. Marks ticket as verified once.',
    tags=['Staff Events']
)
class StaffVerifyTicketView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class = StaffTicketVerifySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_id = serializer.validated_data['event_id']
        tracking_number = serializer.validated_data.get('tracking_number')
        qr_data = serializer.validated_data.get('qr_data')

        tickets = Ticket.objects.filter(event_id=event_id)
        ticket = None
        if tracking_number:
            ticket = tickets.filter(tracking_number=tracking_number).first()
        if not ticket and qr_data:
            ticket = tickets.filter(qr_data=qr_data).first()
        if not ticket:
            # try matching by code if qr_data contains UUID-like string
            try:
                import uuid
                possible = uuid.UUID(qr_data)
                ticket = tickets.filter(code=possible).first()
            except Exception:
                pass

        if not ticket:
            return Response({'detail': 'Ticket not found for that event'}, status=status.HTTP_404_NOT_FOUND)

        if ticket.is_verified:
            data = TicketSerializer(ticket, context={'request': request}).data
            return Response({'message': 'Ticket already verified', 'ticket': data}, status=status.HTTP_200_OK)

        # Mark verified
        ticket.is_verified = True
        from django.utils import timezone as djtz
        ticket.verified_at = djtz.now()
        ticket.verified_by = request.user
        ticket.save(update_fields=['is_verified', 'verified_at', 'verified_by'])

        data = TicketSerializer(ticket, context={'request': request}).data
        return Response({'message': 'Ticket verified', 'ticket': data}, status=status.HTTP_200_OK)


def build_staff_tokens(user, staff):
    refresh = RefreshToken.for_user(user)
    created_at = staff.created_at
    refresh['email'] = user.email
    refresh['username'] = user.username
    # include role claim for staff
    refresh['role'] = 'staff'
    refresh['staff'] = {
        'id': staff.id,
        'full_name': staff.full_name,
        'email': user.email,
        'username': user.username,
        'phone_number': staff.phone_number,
        'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
    }
    return refresh, str(refresh.access_token), str(refresh)


@extend_schema(
    request=StaffRegistrationSerializer,
    responses=StaffAuthResponseSerializer,
    description="Register a new staff member with required details.",
)
class StaffRegistrationView(GenericAPIView):
    serializer_class = StaffRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        full_name = request.data.get('full_name', '')
        phone_number = request.data.get('phone_number', '')
        staff = Staff.objects.create(
            user=user,
            full_name=full_name,
            phone_number=phone_number
        )
        refresh, access_token, refresh_token = build_staff_tokens(user, staff)
        staff_data = StaffDetailSerializer(staff).data
        response_data = {
            'staff': staff_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Staff registered successfully'
        }
        response = Response(response_data, status=status.HTTP_201_CREATED)
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
        return response


@extend_schema(
    request=StaffLoginSerializer,
    responses=StaffAuthResponseSerializer,
    description="Staff login. Returns staff details and tokens.",
)
class StaffLoginView(GenericAPIView):
    serializer_class = StaffLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        try:
            staff = Staff.objects.get(user=user)
        except Staff.DoesNotExist:
            raise serializers.ValidationError({'detail': 'Staff profile not found.'})
        refresh, access_token, refresh_token = build_staff_tokens(user, staff)
        staff_data = StaffDetailSerializer(staff).data
        response_data = {
            'staff': staff_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Login successful'
        }
        response = Response(response_data, status=status.HTTP_200_OK)
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
        return response


@extend_schema_view(
    list=extend_schema(
        description='List all staff members (superuser only).',
        responses=StaffDetailSerializer(many=True),
    ),
    retrieve=extend_schema(
        description='Retrieve a single staff member by ID (superuser only).',
        responses=StaffDetailSerializer,
    ),
    update=extend_schema(
        description='Update a staff member details including role (superuser only).',
        request=StaffDetailSerializer,
        responses=StaffUpdateResponseSerializer,
    ),
    partial_update=extend_schema(
        description='Partially update a staff member details including role (superuser only).',
        request=StaffDetailSerializer,
        responses=StaffUpdateResponseSerializer,
    ),
    destroy=extend_schema(
        description='Delete a staff member profile and their associated User account (superuser only).',
        responses={200: StaffDeleteResponseSerializer},
    ),
)
@extend_schema(tags=['Staff Management'])
class StaffViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    queryset = Staff.objects.all()
    serializer_class = StaffDetailSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            'message': 'Staff profile updated successfully',
            'staff': serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'Staff deleted successfully'
        }, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        user = instance.user
        user.delete()


def _add_months(source_date, months):
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    return source_date.replace(year=year, month=month, day=1)


@extend_schema(
    responses=SuperuserDashboardResponseSerializer,
    description='Get the super admin dashboard summary, monthly revenue, and recent completed orders.',
    tags=['Staff Dashboard'],
)
class SuperuserDashboardView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        current_month = today.replace(day=1)

        active_events_qs = Event.objects.filter(
            Q(date__gt=today) | Q(date=today, time__gte=timezone.localtime().time())
        )
        completed_orders = Order.objects.filter(status='completed')

        total_revenue = completed_orders.aggregate(total=Sum('total_amount'))['total'] or 0
        tickets_sold = Ticket.objects.filter(order__status='completed').count()
        checked_in = Ticket.objects.filter(is_verified=True).count()

        month_starts = [_add_months(current_month, offset) for offset in range(-7, 1)]
        month_end = _add_months(current_month, 1)
        revenue_rows = (
            completed_orders
            .filter(created_at__gte=month_starts[0], created_at__lt=month_end)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(revenue=Sum('total_amount'))
            .order_by('month')
        )

        revenue_map = {}
        for row in revenue_rows:
            month_value = row['month']
            month_key = month_value.strftime('%Y-%m')
            revenue_map[month_key] = row['revenue'] or 0

        monthly_revenue = [
            {
                'month': month_start.strftime('%b'),
                'revenue': revenue_map.get(month_start.strftime('%Y-%m'), 0),
            }
            for month_start in month_starts
        ]

        recent_orders = []
        for order in completed_orders.select_related('event', 'user').order_by('-created_at')[:5]:
            customer = getattr(getattr(order.user, 'customer', None), 'full_name', '') or order.user.get_full_name() or order.user.username
            event_image = ''
            if order.event and order.event.image:
                try:
                    event_image = request.build_absolute_uri(order.event.image.url)
                except Exception:
                    event_image = order.event.image.url

            recent_orders.append({
                'order_id': f'ORD-{order.id}',
                'event': order.event.title,
                'event_image': event_image,
                'customer': customer,
                'quantity': order.quantity,
                'amount': order.total_amount,
                'payment_status': order.status,
                'created_at': order.created_at,
            })

        response_data = {
            'summary': {
                'total_revenue': total_revenue,
                'tickets_sold': tickets_sold,
                'active_events': active_events_qs.count(),
                'checked_in': checked_in,
            },
            'monthly_revenue': monthly_revenue,
            'recent_orders': recent_orders,
        }
        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema(
    request=SuperuserLoginSerializer,
    responses=SuperuserAuthResponseSerializer,
    description="Superuser login using email and password. Returns user details and tokens.",
)

class SuperuserOdersView(ListAPIView):
    permission_classes = [IsAuthenticated, IsSuperUser]
    serializer_class = OrderSerializer
    
    @extend_schema(
        tags=["Superuser"],
        summary="Order List",
        description="Retrieve all orders.",
        responses={200: OrderSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Order.objects.filter(status='completed').select_related('user', 'event').order_by('-created_at')


class SuperuserLoginView(GenericAPIView):
    serializer_class = SuperuserLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Prepare superuser detail data
        super_data = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined,
        }

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        # include role claim for superuser/admin
        try:
            refresh['role'] = 'admin'
        except Exception:
            pass
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response_data = {
            'superuser': super_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Superuser login successful'
        }

        response = Response(response_data, status=status.HTTP_200_OK)
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
        return response


@extend_schema(
    responses=SuperuserDetailSerializer,
    description="Get the logged-in superuser profile.",
)
class SuperuserProfileView(GenericAPIView):
    serializer_class = SuperuserDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_superuser(self):
        user = self.request.user
        if not user.is_superuser:
            return None
        return user

    def get(self, request, *args, **kwargs):
        user = self.get_superuser()
        if user is None:
            return Response({'detail': 'User is not a superuser.'}, status=status.HTTP_403_FORBIDDEN)
        response_data = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(
        request=SuperuserProfileSerializer,
        responses=SuperuserProfileResponseSerializer,
        description="Update the logged-in superuser profile information.",
    )
    def put(self, request, *args, **kwargs):
        user = self.get_superuser()
        if user is None:
            return Response({'detail': 'User is not a superuser.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = SuperuserProfileSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
            user.username = data['email']

        user.save(update_fields=['first_name', 'last_name', 'email', 'username'])

        response_data = {
            'superuser': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'is_superuser': user.is_superuser,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined,
            },
            'message': 'Profile updated successfully',
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)


class SuperuserPasswordChangeView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SuperuserPasswordChangeSerializer,
        responses=SuperuserPasswordChangeResponseSerializer,
        description="Change the logged-in superuser password."
    )
    def post(self, request, *args, **kwargs):

        user = request.user

        # ❌ Not superuser error
        if not user.is_superuser:
            return Response(
                {
                    "success": False,
                    "message": "Only superusers can change password",
                    "data": None
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SuperuserPasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )

        # ❌ Validation error response
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation failed",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ change password
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        return Response(
            {
                "success": True,
                "message": "Password changed successfully",
                "data": {
                    "user_id": user.id,
                    "username": user.username
                }
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    responses=OwnProfileResponseSerializer,
    description='Get the authenticated user own profile details. Supports customer, staff, and superuser accounts.',
    tags=['Staff Profile'],
)
class MyProfileView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        profile_type = 'admin'
        role = 'admin'
        profile = None

        customer = Customer.objects.filter(user=user).first()
        staff = Staff.objects.filter(user=user).first()

        if customer:
            profile_type = 'customer'
            role = 'customer'
            profile = {
                'id': customer.id,
                'full_name': customer.full_name,
                'phone_number': customer.phone_number,
                'gender': customer.gender,
                'date_of_birth': customer.date_of_birth,
                'created_at': customer.created_at,
                'updated_at': customer.updated_at,
            }
        elif staff:
            profile_type = 'staff'
            role = getattr(staff, 'role', 'staff') or 'staff'
            profile = {
                'id': staff.id,
                'full_name': staff.full_name,
                'phone_number': staff.phone_number,
                'role': role,
                'created_at': staff.created_at,
                'updated_at': staff.updated_at,
            }
        elif user.is_superuser:
            profile_type = 'admin'
            role = 'admin'
            profile = {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined,
            }

        response_data = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'role': role,
            'profile_type': profile_type,
            'date_joined': user.date_joined,
            'profile': profile,
            'message': 'Profile fetched successfully',
        }
        return Response(response_data, status=status.HTTP_200_OK)



@extend_schema(
    tags=["Banner"],
    summary="Get latest 5 banners",
    responses={
        200: BannerSerializer(many=True)
    }
)
class LatestBannerListView(generics.ListAPIView):
    serializer_class = BannerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Banner.objects.all()[:5]

@extend_schema(
    tags=["Banner"],
    summary="created Banners",
    request=BannerSerializer,
    responses={
        201: BannerSerializer,
        400: None,
        403: OpenApiResponse(description="permission denied "),
    
    }
)
class BannerCreateView(generics.CreateAPIView):
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

@extend_schema(
    tags=["Banner"],
    summary="Update or Delete Banner",
    request=BannerSerializer,
    responses={
        200: BannerSerializer,
        403: OpenApiResponse(description="Permission denied"),
        404: OpenApiResponse(description="Banner not found")
    }
)
class BannerUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]


@extend_schema(
    tags=["Singer"],
    summary="Get singers",
    responses={
        200: SingerSerializer(many=True)
    }
)

class SingerListView(generics.ListAPIView):
    serializer_class = SingerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Singer.objects.all()

@extend_schema(
    tags=["Singer"],
    summary="created Singers",
    request=SingerSerializer,
    responses={
        201: SingerSerializer,
        400: None,
        403: OpenApiResponse(description="permission denied "),
    
    }
)

class SingerCreateView(generics.CreateAPIView):
    queryset = Singer.objects.all()
    serializer_class = SingerSerializer
    permission_classes = [IsAuthenticated, IsSuperUser] 


@extend_schema(
    tags=["Singer"],
    summary="Update or Delete Singer",
    request=SingerSerializer,
    responses={
        200: SingerSerializer,
        403: OpenApiResponse(description="Permission denied"),
        404: OpenApiResponse(description="Singer not found")
    }
)

class SingerUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Singer.objects.all()
    serializer_class = SingerSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]


@extend_schema(
    tags=["AboutUs"],
    summary="Get About Us content",
    responses={
        200: AboutUsSerializer(many=True)
    }
)
class AboutUsListView(generics.ListAPIView):
    serializer_class = AboutUsSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return AboutUs.objects.all()[:1]

@extend_schema(
    tags=["AboutUs"],
    summary="Create About Us content",
    request=AboutUsSerializer,
    responses={
        201: AboutUsSerializer,
        400: None,
        403: OpenApiResponse(description="permission denied "),
    
    }
)
class AboutUsCreateView(generics.CreateAPIView):
    queryset = AboutUs.objects.all()
    serializer_class = AboutUsSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

@extend_schema(
    tags=["AboutUs"],
    summary="Update or Delete About Us content",
    request=AboutUsSerializer,
    responses={
        200: AboutUsSerializer,
        403: OpenApiResponse(description="Permission denied"),
        404: OpenApiResponse(description="Content not found")
    }
)
class AboutUsUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AboutUs.objects.all()
    serializer_class = AboutUsSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]



@extend_schema(
    tags=["PrivacyPolicy"],
    summary="Get Privacy Policy content",
    responses={
        200: PrivecyPolicySerializer(many=True)
    }
)

class PrivacyPolicyListView(generics.ListAPIView):
    serializer_class = PrivecyPolicySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return PrivecyPolicy.objects.all()[:1]

@extend_schema(
    tags=["PrivacyPolicy"],
    summary="Create Privacy Policy content",
    request=PrivecyPolicySerializer,
    responses={
        201: PrivecyPolicySerializer,
        400: None,
        403: OpenApiResponse(description="permission denied "),
    
    }
)

class PrivacyPolicyCreateView(generics.CreateAPIView):
    queryset = PrivecyPolicy.objects.all()
    serializer_class = PrivecyPolicySerializer
    permission_classes = [IsAuthenticated, IsSuperUser]


@extend_schema(
    tags=["PrivacyPolicy"],
    summary="Update or Delete Privacy Policy content",
    request=PrivecyPolicySerializer,
    responses={
        200: PrivecyPolicySerializer,
        403: OpenApiResponse(description="Permission denied"),
        404: OpenApiResponse(description="Content not found")
    }
)

class PrivacyPolicyUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PrivecyPolicy.objects.all()
    serializer_class = PrivecyPolicySerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

@extend_schema(
    tags=["TermsAndConditions"],
    summary="Get Terms and Conditions content",
    responses={
        200: TremsAndConditionSerializer(many=True)
    }
)
class TremsAndConditionListView(generics.ListAPIView):
    serializer_class = TremsAndConditionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return TremsAndCondition.objects.all()[:1]


@extend_schema(
    tags=["TermsAndConditions"],
    summary="Create Terms and Conditions content",
    request=TremsAndConditionSerializer,
    responses={
        201: TremsAndConditionSerializer,
        400: None,
        403: OpenApiResponse(description="permission denied "),
    
    }
)

class TremsAndConditionCreateView(generics.CreateAPIView):
    queryset = TremsAndCondition.objects.all()
    serializer_class = TremsAndConditionSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]


@extend_schema(
    tags=["TermsAndConditions"],
    summary="Update or Delete Terms and Conditions content",
    request=TremsAndConditionSerializer,
    responses={
        200: TremsAndConditionSerializer,
        403: OpenApiResponse(description="Permission denied"),
        404: OpenApiResponse(description="Content not found")
    }
)
class TremsAndConditionUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TremsAndCondition.objects.all()
    serializer_class = TremsAndConditionSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]


class SendOTPView(APIView):

    @extend_schema(
        request=SendOTPSerializer,
        responses={
            200: {"type": "object"},
            400: {"type": "object"},
            404: {"type": "object"},
        },
        tags=["Forgot Password"],
        description="Send OTP to registered email"
    )
    def post(self, request):
        email = request.data.get("email")

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "User not found"}, status=404)

        otp = str(random.randint(100000, 999999))

        # 🔥 always update latest OTP (overwrite old one)
        PasswordResetOTP.objects.update_or_create(
            email=email,
            defaults={
                "otp": otp,
                "is_verified": False,
            }
        )

        send_mail(
            "Password Reset OTP",
            f"Your OTP is: {otp}",
            None,
            [email]
        )

        return Response({"message": "OTP sent successfully"}, status=200)


class VerifyOTPView(APIView):

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={
            200: {"type": "object"},
            400: {"type": "object"},
        },
        tags=["Forgot Password"],
        description="Verify OTP"
    )
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        otp_obj = PasswordResetOTP.objects.filter(email=email).first()

        if not otp_obj:
            return Response({"error": "OTP not found"}, status=400)

        if otp_obj.is_expired():
            return Response({"error": "OTP expired"}, status=400)

        if otp_obj.otp != otp:
            return Response({"error": "Invalid OTP"}, status=400)

        otp_obj.is_verified = True
        otp_obj.save()

        return Response({"message": "OTP verified successfully"}, status=200)


class ResetPasswordView(APIView):

    @extend_schema(
        request=ResetPasswordSerializer,
        responses={
            200: {"type": "object"},
            400: {"type": "object"},
            404: {"type": "object"},
        },
        tags=["Forgot Password"],
        description="Reset password after OTP verification"
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        otp_obj = PasswordResetOTP.objects.filter(
            email=email,
            is_verified=True
        ).first()

        if not otp_obj:
            return Response({"error": "OTP not verified"}, status=400)

        user = User.objects.filter(email=email).first()

        if not user:
            return Response({"error": "User not found"}, status=404)

        user.set_password(password)
        user.save()

        # cleanup after success
        PasswordResetOTP.objects.filter(email=email).delete()

        return Response({"message": "Password reset successful"}, status=200)