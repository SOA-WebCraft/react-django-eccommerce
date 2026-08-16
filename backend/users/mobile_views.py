import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils.crypto import salted_hmac
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils import timezone
from django.urls import reverse
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    UserSerializer,
)
from .models import MobileSocialExchange, SocialIdentity
from .services import send_password_reset_emails
from .social_auth import (
    SocialAuthError,
    login_or_create_social_user,
    oauth_client,
    profile_from_token,
    provider_is_configured,
)


User = get_user_model()
INVALID_CREDENTIALS = 'Invalid email or password.'
INVALID_EXCHANGE_CODE = 'This sign-in code is invalid or has expired.'


def mobile_token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'access_expires_in': 15 * 60,
        'refresh_expires_in': 30 * 24 * 60 * 60,
        'user': UserSerializer(user).data,
    }


def mobile_social_callback_url():
    path = reverse('mobile-social-google-callback')
    return f'{settings.MOBILE_SOCIAL_CALLBACK_BASE_URL}{path}'


def exchange_code_hash(code):
    return salted_hmac('users.mobile-social-exchange', code).hexdigest()


def deep_link_response(redirect_uri, **params):
    separator = '&' if '?' in redirect_uri else '?'
    response = HttpResponse(status=302)
    response['Location'] = f'{redirect_uri}{separator}{urlencode(params)}'
    return response


class MobileRegistrationView(generics.CreateAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegistrationSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'mobile_registration'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class MobileTokenView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'mobile_login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        matches = list(User.objects.filter(
            email__iexact=serializer.validated_data['email'],
        )[:2])
        user = None
        if len(matches) == 1:
            user = authenticate(
                request=request,
                username=matches[0].get_username(),
                password=serializer.validated_data['password'],
            )
        if user is None or user.is_staff:
            return Response(
                {'detail': INVALID_CREDENTIALS},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(mobile_token_payload(user))


class MobileSocialGoogleStartView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'mobile_social_start'

    def get(self, request):
        redirect_uri = request.query_params.get('redirect_uri', '')
        if redirect_uri not in settings.MOBILE_SOCIAL_REDIRECT_URIS:
            return Response(
                {'redirect_uri': ['This redirect URI is not allowed.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not provider_is_configured(SocialIdentity.Provider.GOOGLE):
            return Response(
                {'detail': 'Google sign-in is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        request.session['mobile_social_redirect_uri'] = redirect_uri
        return oauth_client(SocialIdentity.Provider.GOOGLE).authorize_redirect(
            request,
            mobile_social_callback_url(),
        )


class MobileSocialGoogleCallbackView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        redirect_uri = request.session.pop('mobile_social_redirect_uri', None)
        if redirect_uri not in settings.MOBILE_SOCIAL_REDIRECT_URIS:
            return Response(
                {'detail': 'The mobile sign-in session is invalid or expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.query_params.get('error'):
            return deep_link_response(redirect_uri, error='access_denied')
        try:
            client = oauth_client(SocialIdentity.Provider.GOOGLE)
            token = client.authorize_access_token(request)
            profile = profile_from_token(
                SocialIdentity.Provider.GOOGLE,
                client,
                token,
            )
            user = login_or_create_social_user(
                SocialIdentity.Provider.GOOGLE,
                profile,
            )
            if user.is_staff:
                raise SocialAuthError(
                    'Staff accounts cannot use mobile authentication.'
                )
            raw_code = secrets.token_urlsafe(32)
            now = timezone.now()
            MobileSocialExchange.objects.filter(expires_at__lte=now).delete()
            MobileSocialExchange.objects.create(
                user=user,
                provider=SocialIdentity.Provider.GOOGLE,
                code_hash=exchange_code_hash(raw_code),
                redirect_uri=redirect_uri,
                expires_at=now + timedelta(minutes=2),
            )
            return deep_link_response(redirect_uri, code=raw_code)
        except SocialAuthError:
            return deep_link_response(redirect_uri, error='account_unavailable')
        except Exception:
            return deep_link_response(redirect_uri, error='authentication_failed')


class MobileSocialExchangeSerializer(serializers.Serializer):
    code = serializers.CharField(trim_whitespace=True, max_length=200)


class MobileSocialExchangeView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'mobile_social_exchange'

    @transaction.atomic
    def post(self, request):
        serializer = MobileSocialExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        exchange = MobileSocialExchange.objects.select_for_update().filter(
            code_hash=exchange_code_hash(serializer.validated_data['code']),
        ).select_related('user').first()
        if (
            exchange is None
            or exchange.consumed_at is not None
            or exchange.expires_at <= now
            or not exchange.user.is_active
            or exchange.user.is_staff
        ):
            return Response(
                {'code': [INVALID_EXCHANGE_CODE]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exchange.consumed_at = now
        exchange.save(update_fields=('consumed_at',))
        return Response(mobile_token_payload(exchange.user))


class MobileTokenRefreshView(TokenRefreshView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'mobile_token_refresh'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data['access_expires_in'] = 15 * 60
        response.data['refresh_expires_in'] = 30 * 24 * 60 * 60
        return response


class MobileLogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class MobileLogoutView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = MobileLogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = UntypedToken(serializer.validated_data['refresh'])
        except TokenError:
            return Response(
                {'refresh': ['Enter a valid, unexpired refresh token.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if token.payload.get('token_type') != 'refresh':
            return Response(
                {'refresh': ['This token is not a refresh token.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        outstanding = OutstandingToken.objects.filter(
            jti=token.payload.get('jti'),
        ).first()
        if outstanding is None:
            return Response(
                {'refresh': ['This refresh token is not recognized.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        BlacklistedToken.objects.get_or_create(token=outstanding)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MobilePasswordResetRequestView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'mobile_password_reset_request'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_password_reset_emails(
            serializer.validated_data['email'],
            base_url=settings.MOBILE_APP_BASE_URL,
        )
        return Response({
            'detail': (
                'If an active account exists for that email address, a '
                'password reset link has been sent.'
            )
        })


class MobilePasswordResetConfirmView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'mobile_password_reset_confirm'

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
