# notifications/routing.py
from django.urls import re_path
from .consumers import TaskProgressConsumer, AlertsConsumer

websocket_urlpatterns = [
    re_path(r'ws/tasks/$', TaskProgressConsumer.as_asgi()),
    re_path(r'ws/alerts/$', AlertsConsumer.as_asgi()),
]
