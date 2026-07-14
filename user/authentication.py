from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication


class CSRFCheck(CsrfViewMiddleware):
    """Return the rejection reason so DRF can produce a JSON 403 response."""

    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    """Apply Django's CSRF validation to a DRF request."""

    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


class CookieTokenAuthentication(TokenAuthentication):
    """
    Authenticate either an ambient cookie token or an Authorization header.

    Cookie credentials require CSRF validation because browsers attach them
    automatically. Explicit Authorization headers remain suitable for
    non-browser API clients and do not require CSRF validation.
    """

    def authenticate(self, request):
        token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)

        if token is None:
            return super().authenticate(request)

        authenticated = self.authenticate_credentials(token)
        enforce_csrf(request)
        return authenticated


def set_auth_cookie(response, token, max_age=None):
    """Set the authentication token in an HttpOnly cookie."""

    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=max_age or settings.AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )
    return response


def clear_auth_cookie(response):
    """Clear the authentication cookie on logout."""

    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response
