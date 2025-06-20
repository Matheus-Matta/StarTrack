from django.urls import re_path
from .consumers import RouteConsumer

websocket_urlpatterns = [
    re_path(r'ws/routes/(?P<scripting_id>\d+)/$', RouteConsumer.as_asgi()),
]