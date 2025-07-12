# tmsapp/scriptApp/views.py

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from tmsapp.models import (
    RouteComposition, RouteCompositionDelivery, CompanyLocation, LocationType, LoadPlan
)


def _build_customer_data(customer):
    """Constrói dados padronizados do cliente."""
    return {
        'id': customer.id,
        'name': customer.full_name
    }


def _build_delivery_stop(delivery, position, delivery_type='delivery'):
    """Constrói dados padronizados de uma parada de entrega."""
    return {
        'id': delivery.id,
        'position': position,
        'status': delivery.status,
        'type': delivery_type,
        'order_number': delivery.order_number,
        'customer': _build_customer_data(delivery.customer),
        'address': delivery.full_address,
        'filial': delivery.filial,
        'lat': delivery.latitude,
        'long': delivery.longitude,
        'total_volume_m3': delivery.total_volume_m3,
        'total_weight_kg': delivery.total_weight_kg,
        'price': delivery.price,
    }


def _build_company_location_stop(company_location):
    """Constrói dados padronizados de uma localização da empresa."""
    try:
        return {
            'id': company_location.id,
            'type': company_location.type,
            'name': company_location.name,
            'address': company_location.full_address(),
            'filial': '-',
            'lat': company_location.latitude,
            'long': company_location.longitude,
        }
    except Exception as e:
        print(f'ERRO ao processar localização da empresa {company_location.id}: {e}')
        return None


def _get_route_stops(route):
    """Obtém todas as paradas de uma rota ordenadas por posição."""
    stops = []
    for route_delivery in route.routedelivery_set.order_by('position'):
        stop = _build_delivery_stop(
            delivery=route_delivery.delivery,
            position=route_delivery.position
        )
        stops.append(stop)
    return stops


def _build_route_data(load_plan):
    """Constrói dados completos de uma rota com seu load plan."""
    route = load_plan.route
    stops = _get_route_stops(route)
    
    return {
        'id': route.id,
        'name': load_plan.name,
        'loadPlan': {
            'id': load_plan.id,
            'name': route.route_area.name,
            'code': load_plan.code
        },
        'geojson': route.geojson,
        'distance_km': route.distance_km,
        'time_min': route.time_min,
        'color': route.route_area.hex_color,
        'stops': stops,
    }


def _get_single_route_data(composition, loadplan_id):
    """Obtém dados de uma única rota específica."""
    load_plan = composition.load_plans_direct.filter(pk=loadplan_id).first()
    
    if not load_plan:
        return None, 'Load plan não encontrado'
        
    if not load_plan.route:
        return None, 'Load plan não possui rota definida'
    
    route_data = _build_route_data(load_plan)
    return [route_data], None


def _get_all_routes_data(composition):
    """Obtém dados de todas as rotas da composição."""
    payload = []
    
    # Adiciona rotas com load plans
    load_plans_with_routes = composition.load_plans_direct.filter(route__isnull=False)
    for load_plan in load_plans_with_routes:
        route_data = _build_route_data(load_plan)
        payload.append(route_data)
    
    # Adiciona localizações da empresa
    company_locations_data = _get_company_locations_data()
    if company_locations_data:
        payload.append(company_locations_data)
    
    return payload


def _get_company_locations_data():
    """Obtém dados das localizações da empresa."""
    company_stops = []
    
    for company_location in CompanyLocation.objects.all():
        stop_data = _build_company_location_stop(company_location)
        if stop_data:  # Apenas adiciona se não houve erro
            company_stops.append(stop_data)
    
    if not company_stops:
        return None
    
    return {
        'id': -2,
        'name': 'Locais da empresa',
        'loadPlan': None,
        'geojson': None,
        'distance_km': 0,
        'time_min': 0,
        'color': 'black',
        'stops': company_stops,
    }


def _get_unassigned_deliveries_data(composition):
    """Obtém dados das entregas não atribuídas a rotas."""
    unassigned_deliveries = RouteCompositionDelivery.objects.filter(
        route_composition=composition,
        load_plan__isnull=True
    ).order_by('sequence')
    
    if not unassigned_deliveries.exists():
        return None
    
    extra_stops = []
    for route_comp_delivery in unassigned_deliveries:
        stop = _build_delivery_stop(
            delivery=route_comp_delivery.delivery,
            position=route_comp_delivery.sequence,
            delivery_type='delivery_unassigned'
        )
        extra_stops.append(stop)
    
    return {
        'id': -1,
        'name': 'Entrega fora de rota',
        'loadPlan': None,
        'geojson': None,
        'distance_km': 0,
        'time_min': 0,
        'color': 'gray',
        'stops': extra_stops,
    }


@login_required
@require_GET
def get_routes_scripting(request, scripting_id):
    """
    Retorna dados das rotas para scripting.
    
    Se loadplan_id for fornecido, retorna apenas essa rota específica.
    Caso contrário, retorna todas as rotas da composição.
    """
    composition = get_object_or_404(RouteComposition, pk=scripting_id)
    loadplan_id = request.GET.get('loadplan_id')
    
    # Processa rota específica se ID fornecido
    if loadplan_id:
        try:
            loadplan_id = int(loadplan_id)
            payload, error_message = _get_single_route_data(composition, loadplan_id)
            
            if error_message:
                return JsonResponse({'error': error_message}, status=404)
                
        except ValueError:
            return JsonResponse({'error': 'ID do load plan inválido'}, status=400)
    
    # Processa todas as rotas
    else:
        payload = _get_all_routes_data(composition)
        
        # Adiciona entregas não atribuídas
        unassigned_data = _get_unassigned_deliveries_data(composition)
        if unassigned_data:
            payload.append(unassigned_data)
    
    return JsonResponse(payload, safe=False)