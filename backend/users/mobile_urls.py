from django.urls import path

from .mobile_views import (
    MobileLogoutView,
    MobilePasswordResetConfirmView,
    MobilePasswordResetRequestView,
    MobileRegistrationView,
    MobileTokenRefreshView,
    MobileTokenView,
)


urlpatterns = [
    path('register/', MobileRegistrationView.as_view(), name='mobile-register'),
    path('token/', MobileTokenView.as_view(), name='mobile-token'),
    path(
        'token/refresh/',
        MobileTokenRefreshView.as_view(),
        name='mobile-token-refresh',
    ),
    path('logout/', MobileLogoutView.as_view(), name='mobile-logout'),
    path(
        'password-reset/',
        MobilePasswordResetRequestView.as_view(),
        name='mobile-password-reset',
    ),
    path(
        'password-reset/confirm/',
        MobilePasswordResetConfirmView.as_view(),
        name='mobile-password-reset-confirm',
    ),
]
