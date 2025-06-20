import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from tmsapp.action import get_geojson_by_ors

logger = logging.getLogger(__name__)

def calc_routes(route, composition, loadplan_id):
    """
    Recalcula geojson, distancia, tempo e paradas de 'route'
    com base no composition e emite um evento via Channels para o grupo
    'scripting_{composition.id}'.
    """
    from tmsapp.scriptApp.models import RouteDelivery, RouteCompositionDelivery, CompanyLocation
    from tmsapp.deliveryApp.models import Delivery

    # 1) monta a query
    seq_qs = RouteCompositionDelivery.objects.filter(
        route_composition=composition,
        load_plan__pk=loadplan_id
    ).order_by('sequence', 'id')

    # 2) se não tem paradas, limpa
    if not seq_qs.exists():
        route.distance_km = 0
        route.time_min    = 0
        route.geojson     = []
        route.points      = []
        route.save()
        RouteDelivery.objects.filter(route=route).delete()
        stops_payload = []
    else:
        # 3) coleta dados completos de cada parada
        stops_payload = []
        coords = []
        for rcd in seq_qs:
            d = rcd.delivery
            lat = float(d.latitude)
            lng = float(d.longitude)
            stops_payload.append({
                'id'          : d.id,
                'position'    : rcd.sequence,
                'order_number': d.order_number,
                'client'      : d.customer.full_name if d.customer else '',
                'address'     : d.full_address,
                'filial'      : d.filial,
                'lat'         : lat,
                'long'        : lng,
                'is_check'    : False,  # ou dalgum campo seu
            })
            coords.append({'lat': lat, 'long': lng, 'order_number': d.order_number})

        # 4) otimiza rota
        departure = (
            route.route_area.departure_location or
            CompanyLocation.objects.filter(is_principal=True, is_active=True).first()
        )
        geojson, duration, distance, ordered = get_geojson_by_ors(coords, departure)

        # 5) atualiza o modelo
        route.distance_km = distance / 1000
        route.time_min    = duration / 60
        route.geojson     = geojson
        route.points      = coords
        route.save()

        # 6) recria RouteDelivery na ordem
        RouteDelivery.objects.filter(route=route).delete()
        for idx, od in enumerate(ordered, start=1):
            d2 = Delivery.objects.get(order_number=od['order_number'])
            RouteDelivery.objects.create(route=route, delivery=d2, position=idx)
