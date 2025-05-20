from django.urls import re_path
from tmsapp.consumers import TaskProgressConsumer, MarkerToggleConsumer

websocket_urlpatterns = [
    re_path(r'ws/tasks/(?P<task_id>[\w-]+)/$', TaskProgressConsumer.as_asgi()),
    re_path(r'ws/marker-toggle/$', MarkerToggleConsumer.as_asgi()),
]
