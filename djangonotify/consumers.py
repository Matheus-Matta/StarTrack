# notifications/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

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
