from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegistrationSerializer,
    StaffCustomerDetailSerializer,
    StaffCustomerListSerializer,
    UserSerializer,
    RoleSerializer,
    StaffUserSerializer,
    allowed_permissions,
)
from .services import send_password_reset_emails, send_staff_invitation
from .social_auth import (
    PROVIDERS,
    SocialAuthError,
    apple_name,
    callback_url,
    frontend_result_url,
    login_or_create_social_user,
    oauth_client,
    profile_from_token,
    provider_is_configured,
    provider_list,
    safe_destination,
)


User = get_user_model()


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_superuser)


class StaffSettingsUserListView(generics.ListCreateAPIView):
    serializer_class = StaffUserSerializer
    permission_classes = (IsSuperUser,)

    def get_queryset(self):
        return User.objects.filter(is_staff=True).prefetch_related(
            'groups__permissions__content_type',
        ).order_by('-is_superuser', 'username')

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        user = User.objects.get(pk=response.data['id'])
        response.data['invitation_sent'] = send_staff_invitation(user)
        return response


class StaffSettingsUserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = StaffUserSerializer
    permission_classes = (IsSuperUser,)
    http_method_names = ('get', 'patch', 'head', 'options')

    def get_queryset(self):
        return User.objects.filter(is_staff=True).prefetch_related(
            'groups__permissions__content_type',
        )


class StaffSettingsRoleListView(generics.ListCreateAPIView):
    serializer_class = RoleSerializer
    permission_classes = (IsSuperUser,)

    def get_queryset(self):
        return Group.objects.prefetch_related(
            'permissions__content_type',
        ).annotate(member_count=Count('user'))


class StaffSettingsRoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RoleSerializer
    permission_classes = (IsSuperUser,)
    http_method_names = ('get', 'patch', 'delete', 'head', 'options')

    def get_queryset(self):
        return Group.objects.prefetch_related(
            'permissions__content_type',
        ).annotate(member_count=Count('user'))

    def perform_destroy(self, instance):
        if instance.user_set.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'role': 'Remove all staff members before deleting this role.'
            })
        instance.delete()


class StaffSettingsPermissionListView(APIView):
    permission_classes = (IsSuperUser,)

    def get(self, request):
        return Response({'results': [
            {
                'id': item.id,
                'name': item.name,
                'codename': item.codename,
                'app_label': item.content_type.app_label,
            }
            for item in allowed_permissions().order_by(
                'content_type__app_label', 'codename',
            )
        ]})


@method_decorator(csrf_protect, name='dispatch')
class RegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = (permissions.AllowAny,)


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CsrfView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        get_token(request)
        return Response({'detail': 'CSRF cookie set.'})


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response(
                {'detail': 'Invalid username or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SocialProviderListView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        return Response({'results': provider_list()})


class SocialLoginView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def get(self, request, provider):
        if provider not in PROVIDERS:
            return Response({'detail': 'Unknown social provider.'}, status=404)
        if not provider_is_configured(provider):
            return Response(
                {'detail': f'{PROVIDERS[provider]["label"]} sign-in is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        request.session['social_auth_next'] = safe_destination(
            request.query_params.get('next', '/account')
        )
        client = oauth_client(provider)
        extra = {'response_mode': 'form_post'} if provider == 'apple' else {}
        return client.authorize_redirect(
            request,
            callback_url(provider),
            **extra,
        )


@method_decorator(csrf_exempt, name='dispatch')
class SocialCallbackView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def get(self, request, provider):
        return self._complete(request, provider)

    def post(self, request, provider):
        return self._complete(request, provider)

    def _complete(self, request, provider):
        if provider not in PROVIDERS or not provider_is_configured(provider):
            return HttpResponseRedirect(frontend_result_url(False))
        if request.query_params.get('error') or request.data.get('error'):
            return HttpResponseRedirect(frontend_result_url(
                False, message='Sign-in was cancelled or denied.'
            ))
        try:
            client = oauth_client(provider)
            token = client.authorize_access_token(request)
            profile = profile_from_token(provider, client, token)
            if provider == 'apple':
                name = apple_name(request)
                profile.setdefault('given_name', name.get('firstName'))
                profile.setdefault('family_name', name.get('lastName'))
            user = login_or_create_social_user(provider, profile)
            login(
                request,
                user,
                backend='django.contrib.auth.backends.ModelBackend',
            )
            destination = request.session.pop('social_auth_next', '/account')
            return HttpResponseRedirect(frontend_result_url(True, destination))
        except Exception as exc:
            message = str(exc) if isinstance(exc, SocialAuthError) else ''
            return HttpResponseRedirect(frontend_result_url(False, message=message))


def staff_customer_queryset():
    return (
        User.objects.filter(is_staff=False)
        .select_related('profile')
        .annotate(
            order_count=Count('orders', distinct=True),
            total_spent=Coalesce(
                Sum(
                    'orders__total',
                    filter=Q(orders__payment_status='paid'),
                ),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        .order_by('-date_joined')
    )


class StaffCustomerListView(generics.ListAPIView):
    serializer_class = StaffCustomerListSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        queryset = staff_customer_queryset()
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(profile__first_name__icontains=search)
                | Q(profile__last_name__icontains=search)
                | Q(profile__phone__icontains=search)
            )
        customer_status = self.request.query_params.get('status')
        if customer_status:
            if customer_status not in {'active', 'inactive'}:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'status': 'Must be either active or inactive.'
                })
            queryset = queryset.filter(is_active=customer_status == 'active')
        return queryset


class StaffCustomerDetailView(generics.RetrieveAPIView):
    serializer_class = StaffCustomerDetailSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = staff_customer_queryset()


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetRequestView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'password_reset_request'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_password_reset_emails(serializer.validated_data['email'])
        return Response({
            'detail': (
                'If an active account exists for that email address, a '
                'password reset link has been sent.'
            )
        })


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetConfirmView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'password_reset_confirm'

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user_id = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        if user is None or not default_token_generator.check_token(
            user,
            data['token'],
        ):
            return Response(
                {'token': 'This password reset link is invalid or has expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(data['new_password'], user=user)
        except DjangoValidationError as exc:
            return Response(
                {'new_password': list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(data['new_password'])
        user.save(update_fields=('password',))
        return Response({'detail': 'Your password has been reset successfully.'})
