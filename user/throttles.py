"""
Rate Limiting Classes for Authentication Endpoints

These throttle classes protect against brute force attacks by limiting
the number of requests a client can make to authentication endpoints.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """
    Rate limit for login attempts.
    Protects against brute force password attacks.
    Default: 5 attempts per minute for anonymous users.
    """
    scope = 'login'
    rate = '5/min'


class RegisterRateThrottle(AnonRateThrottle):
    """
    Rate limit for registration attempts.
    Prevents spam account creation.
    Default: 3 registrations per hour.
    """
    scope = 'register'
    rate = '3/hour'


class PasswordChangeThrottle(UserRateThrottle):
    """
    Rate limit for password change attempts.
    Prevents abuse of password change functionality.
    Default: 5 attempts per hour for authenticated users.
    """
    scope = 'password_change'
    rate = '5/hour'


class ProfileUpdateThrottle(UserRateThrottle):
    """
    Rate limit for profile update requests.
    Prevents excessive profile modifications.
    Default: 20 updates per hour.
    """
    scope = 'profile_update'
    rate = '20/hour'
