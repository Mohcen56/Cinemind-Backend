"""
HTTP-Only Cookie Authentication for DRF

This module provides secure token storage using HTTP-only cookies,
which protects against XSS attacks since JavaScript cannot access
HTTP-only cookies.
"""

from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from django.conf import settings


class CookieTokenAuthentication(TokenAuthentication):
    """
    Custom authentication that reads the token from an HTTP-only cookie
    instead of the Authorization header.
    
    This is more secure than localStorage as HTTP-only cookies cannot
    be accessed by JavaScript, protecting against XSS attacks.
    """
    
    def authenticate(self, request):
        # First try to get token from cookie
        token = request.COOKIES.get('authToken')
        
        if token:
            try:
                return self.authenticate_credentials(token)
            except Exception:
                return None  # Invalid token in cookie, allow anonymous
        
        # Check for Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header and auth_header.startswith('Token '):
            token = auth_header.split(' ', 1)[1]
            try:
                return self.authenticate_credentials(token)
            except Exception:
                return None
        
        # No authentication provided - allow anonymous access
        return None


def set_auth_cookie(response, token, max_age=7*24*60*60):
    """
    Set the authentication token as an HTTP-only cookie.
    
    Args:
        response: Django Response object
        token: Token string to store
        max_age: Cookie lifetime in seconds (default 7 days)
    """
    is_production = not settings.DEBUG
    
    response.set_cookie(
        key='authToken',
        value=token,
        max_age=max_age,
        httponly=True,  # Cannot be accessed by JavaScript - XSS protection
        secure=is_production,  # HTTPS only in production
        samesite='Lax',  # CSRF protection
        path='/',
    )
    return response


def clear_auth_cookie(response):
    """
    Clear the authentication cookie on logout.
    
    Args:
        response: Django Response object
    """
    response.delete_cookie(
        key='authToken',
        path='/',
        samesite='Lax',
    )
    return response
