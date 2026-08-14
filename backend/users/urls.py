from django.urls import path

from .views import (
    CsrfView,
    CurrentUserView,
    EmailAvailabilityView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
    SocialCallbackView,
    SocialLoginView,
    SocialProviderListView,
)


urlpatterns = [
    path('register/', RegistrationView.as_view(), name='user-register'),
    path('email-availability/', EmailAvailabilityView.as_view(), name='user-email-availability'),
    path('csrf/', CsrfView.as_view(), name='user-csrf'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('social-providers/', SocialProviderListView.as_view(), name='user-social-providers'),
    path('social-login/<str:provider>/', SocialLoginView.as_view(), name='user-social-login'),
    path('social-login/<str:provider>/callback/', SocialCallbackView.as_view(), name='user-social-callback'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='user-password-reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='user-password-reset-confirm'),
    path('me/', CurrentUserView.as_view(), name='user-me'),
]
