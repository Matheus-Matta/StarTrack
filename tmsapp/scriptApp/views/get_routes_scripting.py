# tmsapp/scriptApp/views.py

from django.shortcuts           import get_object_or_404
from django.http                import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http  import require_GET

from tmsapp.models import (
    RouteComposition,
    LoadPlan
)

@login_required
@require_GET
def get_routes_scripting(request, scripting_id):
    """
    Retorna um JSON com todas as rotas (via LoadPlan → Route → RouteDelivery)
    e suas paradas, para a composição de rota indicada.
    """
    # 1) busca a composição (sem prefetch mirabolante)
    comp = get_object_or_404(RouteComposition, pk=scripting_id)

    # 2) carrega só os LoadPlans que pertencem a essa composição
    #    + otimiza fetch de rota, área e paradas (com customer)
    lps = (
        LoadPlan.objects
        .filter(routecompositiondelivery__route_composition=comp)
        .select_related('route__route_area')
        .prefetch_related('route__routedelivery_set__delivery__customer')
        .distinct()
    )

    payload = []
    for lp in comp.load_plans.all():
        route = lp.route
        stops = []
        for rd in route.routedelivery_set.all().order_by('position'):
            d = rd.delivery
            stops.append({
                'id'          : d.id,
                'position'    : rd.position,
                'order_number': d.order_number,
                'client'      : d.customer.full_name,
                'address'     : d.full_address,
                'filial'      : d.filial,
                'lat'         : d.latitude,
                'long'        : d.longitude,
            })

        payload.append({
            'id'         : route.id,           # <-- incluído
            'name'       : route.name,
            'geojson'    : route.geojson,
            'distance_km': route.distance_km,
            'time_min'   : route.time_min,
            'color'      : route.route_area.hex_color,
            'stops'      : stops,
        })

    return JsonResponse(payload, safe=False)

