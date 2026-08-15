from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
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
from .services import send_password_reset_emails


User = get_user_model()
INVALID_CREDENTIALS = 'Invalid email or password.'


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
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'access_expires_in': 15 * 60,
            'refresh_expires_in': 30 * 24 * 60 * 60,
            'user': UserSerializer(user).data,
        })


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
