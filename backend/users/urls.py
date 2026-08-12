from django.urls import path

from .views import (
    CsrfView,
    CurrentUserView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
)


urlpatterns = [
    path('register/', RegistrationView.as_view(), name='user-register'),
    path('csrf/', CsrfView.as_view(), name='user-csrf'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='user-password-reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='user-password-reset-confirm'),
    path('me/', CurrentUserView.as_view(), name='user-me'),
]
