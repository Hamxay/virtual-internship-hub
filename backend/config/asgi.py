"""ASGI: HTTP via Django, WebSockets via Channels (notification fan-out)."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from config.middleware import TokenAuthMiddlewareStack

django_asgi_app = get_asgi_application()

from notifications.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        'websocket': TokenAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns),
        ),
    }
)
