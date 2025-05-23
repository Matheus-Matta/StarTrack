# notifications/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from .models import Notification
import json

class TaskProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user or not user.is_authenticated:
            # fecha se não estiver autenticado
            await self.close(code=4401)
            return

        # grupo único por usuário
        self.group_name = f"tasks_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_progress(self, event):
        # encaminha o JSON direto
        await self.send(text_data=event['text'])


class AlertsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = f"alerts_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_alert(self, event):
        await self.send(text_data=event['text'])

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        content = json.loads(text_data)
        action = content.get("action")
        if action == "mark_read":
            notif_id = content.get("notification_id")
            if notif_id:
                await database_sync_to_async(
                    Notification.objects.filter(pk=notif_id).update
                )(read=True)
