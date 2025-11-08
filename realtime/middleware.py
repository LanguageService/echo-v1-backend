"""
Custom Middleware for Django Channels
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken
from dj_rest_auth.app_settings import api_settings as dj_rest_auth_settings

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_key):
    """
    Asynchronously gets a user from a JWT access token.
    Returns an AnonymousUser if the token is invalid or the user doesn't exist.
    """
    if not token_key:
        return AnonymousUser()
    try:
        # Use AccessToken to validate the token's signature and expiration
        token = AccessToken(token_key)
        # Get the user_id from the token payload
        user_id = token.get(settings.SIMPLE_JWT['USER_ID_CLAIM'])
        user = User.objects.get(**{settings.SIMPLE_JWT['USER_ID_FIELD']: user_id})
        if not user.is_active:
            return AnonymousUser()
        return user
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()

class JWTAuthMiddleware:
    """
    Custom middleware for Django Channels to authenticate users via a JWT access
    token passed in an HttpOnly cookie. It also supports token authentication
    via query string as a fallback for non-browser clients.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = None
        cookie_name = dj_rest_auth_settings.JWT_AUTH_COOKIE
        
        headers = dict(scope['headers'])
        if b'cookie' in headers:
            cookies = headers[b'cookie'].decode()
            for cookie_str in cookies.split(';'):
                cookie_str = cookie_str.strip()
                if cookie_str.startswith(cookie_name + '='):
                    token = cookie_str.split('=', 1)[1]
                    break
        
        if not token:
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = parse_qs(query_string)
            token = query_params.get("token", [None])[0]

        scope['user'] = await get_user_from_token(token)
        return await self.app(scope, receive, send)
