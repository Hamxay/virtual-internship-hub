"""Channels: authenticate WebSocket connections with ``?token=<JWT>`` (no Authorization header)."""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async


@database_sync_to_async
def _user_from_access_token(token_key: str):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import AnonymousUser
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    User = get_user_model()
    if not token_key:
        return AnonymousUser()
    try:
        access = AccessToken(token_key)
        user_id = access['user_id']
        return User.objects.get(pk=user_id)
    except (TokenError, InvalidToken, KeyError, User.DoesNotExist):
        return AnonymousUser()


class TokenAuthMiddleware:
    """Populate ``scope['user']`` from ``?token=<jwt>`` query string."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            return await self.inner(scope, receive, send)

        query_string = scope.get('query_string', b'').decode('utf-8')
        params = parse_qs(query_string)
        token = (params.get('token') or [None])[0]
        user = await _user_from_access_token(token or '')
        scope = {**scope, 'user': user}
        return await self.inner(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    """Channels stack entrypoint wrapping ``TokenAuthMiddleware``."""
    return TokenAuthMiddleware(inner)
