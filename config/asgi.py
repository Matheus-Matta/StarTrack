# project/asgi.py

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import djangonotify.routing       as notify_routing
import tmsapp.scriptApp.routing    as map_routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            notify_routing.websocket_urlpatterns
          + map_routing.websocket_urlpatterns
        )
    ),
})
