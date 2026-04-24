"""
ASGI config — HTTP (Django) + WebSocket (Channels) for FR10 notifications.
"""
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from config.middleware import TokenAuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from notifications.routing import websocket_urlpatterns  # noqa: E402 — after Django setup

application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        'websocket': TokenAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns),
        ),
    }
)
