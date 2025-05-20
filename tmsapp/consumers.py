import json
from channels.generic.websocket import AsyncWebsocketConsumer
from tmsapp.models import Delivery
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist

class TaskProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.group_name = f'task_progress_{self.task_id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        print(f"Task ID: {self.task_id}")
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def task_progress_update(self, event):
        await self.send(text_data=json.dumps({
            'progress': event['progress'],
            'percent': event['percent'],
            'composition_id': event.get('composition_id'),
        }))


class MarkerToggleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("marker_updates", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("marker_updates", self.channel_name)


    async def receive(self, text_data):
        data = json.loads(text_data)
        delivery_id = data.get("delivery_id")

        try:
            delivery = await sync_to_async(Delivery.objects.get)(id=delivery_id)
            delivery.is_check = not delivery.is_check
            await sync_to_async(delivery.save)()
            await self.channel_layer.group_send(
                "marker_updates",
                {
                    "type": "toggle.marker",
                    "delivery_id": delivery_id,
                    "is_check": delivery.is_check,
                }
            )
        except Delivery.DoesNotExist:
            await self.send(text_data=json.dumps({
                "error": f"Entrega com ID {delivery_id} não encontrada."
            }))

    async def toggle_marker(self, event):
        await self.send(text_data=json.dumps({
            "delivery_id": event["delivery_id"],
            "is_check": event["is_check"],
        }))