from rest_framework.authentication import SessionAuthentication as BaseSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class SessionAuthentication(BaseSessionAuthentication):
    def authenticate_header(self, request):
        return 'Session'


class MobileJWTAuthentication(JWTAuthentication):
    """Authenticate native clients while keeping dashboard APIs session-only."""

    def authenticate(self, request):
        if request.path.startswith('/api/staff/'):
            return None
        authenticated = super().authenticate(request)
        if authenticated is not None and authenticated[0].is_staff:
            raise AuthenticationFailed(
                'Staff accounts must use session authentication.'
            )
        return authenticated
