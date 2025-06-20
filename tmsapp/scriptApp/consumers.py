# tmsapp/scriptApp/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from django.shortcuts import get_object_or_404
from tmsapp.scriptApp.models import RouteComposition
from tmsapp.fleetApp.models import LoadPlan
from tmsapp.fleetApp.views.load import LoadPlanService
from django.http import JsonResponse

class RouteConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.scripting_id = self.scope['url_route']['kwargs']['scripting_id']
        self.group_name = f"routes_{self.scripting_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        msg = json.loads(text_data)
        action = msg.get('action')
        data   = msg.get('data', {})

        if action == 'update_route':
            result = await self._ws_update_loadplan_delivery(data)
            await self.send(text_data=json.dumps(result))

        else:
            await self.send(text_data=json.dumps({
                'error': f"Ação '{action}' não reconhecida."
            }))

    @database_sync_to_async
    def _ws_update_loadplan_delivery(self, payload):
        """
        Replica a lógica de update_loadplan_delivery da view, mas retorna
        um dicionário para enviar de volta via WS.
        """
        try:
            delivery_id = payload.get('delivery_id', [])
            old_loadplan_id  = int(payload.get('old_loadplan_id'))
            new_loadplan_id  = int(payload.get('new_loadplan_id'))
            scripting_id = payload.get('scripting_id')

            service = LoadPlanService()
            
            if old_loadplan_id and new_loadplan_id or new_loadplan_id==0:
               service.update_plan_deliveries(
                   [delivery_id], old_loadplan_id, scripting_id, 'DELETE'
               )
               
            if new_loadplan_id != 0:
                service.update_plan_deliveries(
                    [delivery_id], new_loadplan_id, scripting_id, 'POST'
                )

        except Exception as e:
            print(f"Erro inesperado na view update_loadplan_delivery: {str(e)}")

    async def reload_map(self, event):
        """
        Handler para action='reload_map'.
        Envia para o cliente o payload em event['data'].
        """
        payload = event.get("data", {})
        await self.send(text_data=json.dumps(payload))
    
    async def update_route(self, event):
        """
        Handler para action='update_route'.
        Envia para o cliente o GeoJSON em event['data'].
        """
        await self.send(text_data=json.dumps({
            'action': 'update_route',
            'data': event['data']
        }))
