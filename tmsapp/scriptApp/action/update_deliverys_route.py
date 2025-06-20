# tmsapp/utils.py
import logging
import json
import decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from tmsapp.models import RouteDelivery, CompanyLocation
from tmsapp.scriptApp.models.RouteComposition import RouteCompositionDelivery, RouteComposition
from tmsapp.deliveryApp.models import Delivery
from tmsapp.scriptApp.action import get_geojson_by_ors

logger = logging.getLogger(__name__)

def _decimal_to_primitive(obj):
    """
    Converte Recursivamente:
      - Decimal -> float
      - listas e dicts são varridos elemento a elemento
    """
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_decimal_to_primitive(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _decimal_to_primitive(v) for k, v in obj.items()}
    return obj


def update_deliverys_route(delivery_ids, loadplan, composition, method):
    """
    Associa ou desassocia um conjunto de Deliverys a um LoadPlan
    dentro de um RouteComposition.
    """
    with transaction.atomic():
        for delivery_id in delivery_ids:
            try:
                delivery = Delivery.objects.get(pk=delivery_id)
            except Delivery.DoesNotExist:
                continue

            if method == 'DELETE':
                try:
                    rcd = RouteCompositionDelivery.objects.get(
                        delivery=delivery,
                        route_composition=composition,
                        load_plan=loadplan
                    )
                    rcd.load_plan = None
                    rcd.save(update_fields=['load_plan'])
                except RouteCompositionDelivery.DoesNotExist:
                    pass

            else:  # POST (ou qualquer outro => trata como adicionar)
                rcd, created = RouteCompositionDelivery.objects.get_or_create(
                    delivery=delivery,
                    route_composition=composition,
                    defaults={'load_plan': loadplan, 'sequence': 0}
                )
                if not created and rcd.load_plan is None:
                    rcd.load_plan = loadplan
                    rcd.save(update_fields=['load_plan'])

def send_route_update_via_ws(composition, loadplan_id=None):
    comp = get_object_or_404(RouteComposition, pk=composition.id)
    payload = []

    # Se loadplan_id vier None: envia **todos** os load plans
    loadplans = (
        comp.load_plans_direct.all()
        if loadplan_id is None
        else comp.load_plans_direct.filter(pk=loadplan_id)
    )

    # Monta payload de cada rota carregada
    for lp in loadplans:
        if not lp.route:
            continue
        route = lp.route
        stops = [
            {
                'id': d.id,
                'position': rd.position,
                'status': d.status,
                'type': 'delivery',
                'order_number': d.order_number,
                'customer': {'id': d.customer.id, 'name': d.customer.full_name},
                'address': d.full_address,
                'filial': d.filial,
                'lat': float(d.latitude),
                'long': float(d.longitude),
            }
            for rd in route.routedelivery_set.order_by('position')
            for d in [rd.delivery]
        ]
        payload.append({
            'id': route.id,
            'name': lp.name,
            'scripting': {
                'id': comp.id,
                'total_deliveries': comp.deliveries_with_loadplan,
                'total_deliveries_unassigned': comp.deliveries_without_loadplan,
            },
            'loadPlan': {
                'id': lp.id,
                'name': route.route_area.name,
                'code': lp.code,
                'totals': {
                    'deliveries': lp.total_deliveries,
                    'volume_m3': lp.formatted_total_volume_m3,
                    'weight_kg': lp.formatted_total_weight_kg,
                    'value': lp.formatted_total_value,
                    'area_deliveries': lp.total_area_deliveries,
                },
                'is_volume_overloaded': lp.is_volume_overloaded,
                'is_weight_overloaded': lp.is_weight_overloaded,
            },
            'geojson': _decimal_to_primitive(route.geojson),
            'distance_km': float(route.distance_km),
            'time_min': float(route.time_min),
            'color': route.route_area.hex_color,
            'stops': stops,
        })

    # Entregas extra (load_plan is null)
    extra_stops = []
    for rcd in RouteCompositionDelivery.objects.filter(
        route_composition=comp, load_plan__isnull=True
    ).order_by('sequence'):
        d = rcd.delivery
        extra_stops.append({
            'id': d.id,
            'position': rcd.sequence,
            'status': d.status,
            'type': 'delivery_unassigned',
            'order_number': d.order_number,
            'customer': {'id': d.customer.id, 'name': d.customer.full_name},
            'address': d.full_address,
            'filial': d.filial,
            'lat': float(d.latitude),
            'long': float(d.longitude),
        })
    if extra_stops:
        payload.append({
            'id': -1,
            'name': 'Entrega fora de rota',
            'loadPlan': None,
            'geojson': None,
            'distance_km': 0,
            'time_min': 0,
            'color': 'gray',
            'stops': extra_stops,
        })

    # Envia tudo
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"routes_{composition.id}",
        {'type': 'update_route', 'data': _decimal_to_primitive(payload)}
    )