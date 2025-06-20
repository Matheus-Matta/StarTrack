# tmsapp/scriptApp/views.py

from django.shortcuts           import get_object_or_404
from django.http                import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http  import require_GET

from tmsapp.models import (
    RouteComposition, RouteCompositionDelivery, CompanyLocation, LocationType, LoadPlan
)

@login_required
@require_GET
def get_routes_scripting(request, scripting_id):
    comp = get_object_or_404(RouteComposition, pk=scripting_id)
    loadplan_id = request.GET.get('loadplan_id')
    payload = []
    
    # Se um loadplan_id específico foi fornecido, retorna apenas essa rota
    if loadplan_id:
        loadplan_id = int(loadplan_id)
        lp = comp.load_plans_direct.filter(pk=loadplan_id).first()
        
        if not lp:
            return JsonResponse({'error': 'Load plan não encontrado'}, status=404)
            
        # Se o load plan não tem rota, retorna erro
        if not lp.route:
            return JsonResponse({'error': 'Load plan não possui rota definida'}, status=404)
                
        route = lp.route
        stops = []
            
        # Adiciona as paradas da rota
        for rd in route.routedelivery_set.order_by('position'):
            d = rd.delivery
            c = d.customer
            name = c.full_name
            pk = c.id
            stops.append({
                'id'          : d.id,
                'position'    : rd.position,
                'status'      : d.status,
                'type'        : 'delivery',
                'order_number': d.order_number,
                'customer'    : {
                    'id'   : pk,
                    'name' : name
                },
                'address'     : d.full_address,
                'filial'      : d.filial,
                'lat'         : d.latitude,
                'long'        : d.longitude,
            })

        payload.append({
            'id'         : route.id,
            'name'       : lp.name,
            'loadPlan'  : {
                'id': lp.id,
                'name': route.route_area.name,
                'code': lp.code
            },
            'geojson'    : route.geojson,
            'distance_km': route.distance_km,
            'time_min'   : route.time_min,
            'color'      : route.route_area.hex_color,
            'stops'      : stops,
        })
    
    # CASO CONTRÁRIO, retorna todas as rotas
    else:
        # Adiciona todas as rotas com load plans
        for lp in comp.load_plans_direct.filter(route__isnull=False):
            route = lp.route
            stops = []
            for rd in route.routedelivery_set.order_by('position'):
                d = rd.delivery
                c = d.customer
                name = c.full_name
                pk = c.id
                stops.append({
                    'id'          : d.id,
                    'position'    : rd.position,
                    'status'      : d.status,
                    'type'        : 'delivery',
                    'order_number': d.order_number,
                    'customer'    : {
                        'id'   : pk,
                        'name' : name
                    },
                    'address'     : d.full_address,
                    'filial'      : d.filial,
                    'lat'         : d.latitude,
                    'long'        : d.longitude,
                })

            payload.append({
                'id'         : route.id,
                'name'       : lp.name,
                'loadPlan'  : {
                    'id': lp.id,
                    'name': route.route_area.name,
                    'code': lp.code
                },
                'geojson'    : route.geojson,
                'distance_km': route.distance_km,
                'time_min'   : route.time_min,
                'color'      : route.route_area.hex_color,
                'stops'      : stops,
            })
            
        # Adiciona localizações da empresa
        companies = []
        for cl in CompanyLocation.objects.all():
            try:
                companies.append({
                    'id'     : cl.id,
                    'type'   : cl.type,
                    'name'   : cl.name,
                    'address': cl.full_address(),
                    'filial' : '-',
                    'lat'    : cl.latitude,
                    'long'   : cl.longitude,
                })
            except Exception as e:
                print('ERRO:',e)
                continue

        payload.append({
            'id'         : -2,
            'name'       : 'Locais da empresa',
            'loadPlan'   : None,
            'geojson'    : None,
            'distance_km': 0,
            'time_min'   : 0,
            'color'      : "black",
            'stops'      : companies,
        })
        
    # Adiciona entregas extras (fora de rota)
    extra_stops = []
    for rcd in RouteCompositionDelivery.objects.filter(route_composition=comp, load_plan__isnull=True).order_by('sequence'):
        d = rcd.delivery
        c = d.customer
        name = c.full_name
        pk = c.id        
        extra_stops.append({
                'id'          : d.id,
                'position'    : rcd.sequence,
                'status'      : d.status,
                'type'        : 'delivery_unassigned',
                'order_number': d.order_number,
                'customer'    : {
                    'id'   : pk,
                    'name' : name
                },
                'address'     : d.full_address,
                'filial'      : d.filial,
                'lat'         : d.latitude,
                'long'        : d.longitude,
            })

    if extra_stops:
        payload.append({
                'id'         : -1,
                'name'       : 'Entrega fora de rota',
                'loadPlan'   : None,
                'geojson'    : None,
                'distance_km': 0,
                'time_min'   : 0,
                'color'      : 'gray',
                'stops'      : extra_stops,
            })
        


    return JsonResponse(payload, safe=False)
