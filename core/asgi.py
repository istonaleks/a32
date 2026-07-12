# core/asgi.py
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Инициализируем Django до импорта Channels
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from manager.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # Обычные HTTP-запросы — стандартный Django
    'http': django_asgi_app,

    # WebSocket — через AuthMiddlewareStack (сессии/куки передаются автоматически)
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
