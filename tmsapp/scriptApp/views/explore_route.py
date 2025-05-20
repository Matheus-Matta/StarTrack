from tmsapp.models import RouteComposition, RouteDelivery, CompanyLocation  # Sua model atualizada
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from celery.result import AsyncResult
from django.contrib import messages
import json

@login_required
def explore_route(request, composition_id):
    # Busca a composição de rotas pelo ID ou retorna 404
    composition = get_object_or_404(RouteComposition, id=composition_id)

    # Pega todas as rotas associadas
    routes = composition.routes.all()

    # Pega o armazém principal ativo
    try:
        principal_location = CompanyLocation.objects.get(is_principal=True, is_active=True)
    except CompanyLocation.DoesNotExist:
        messages.error(request, 'Nenhuma localização principal de armazém ativa encontrada.')
        return redirect('tmsapp:router')

    # Prepara os dados das rotas para passar ao template
    routes_data = []
    for route in routes:
        stops = []
        
        # Adiciona o armazém principal como a posição 0
        if principal_location:
            stops.append({
                'client': principal_location.name,
                'position': 0,
                'order_number': 'SAIDA',  # ardem deve ser saida para ser marcada no mapa corretament
                'address': principal_location.full_address(),
                'lat': float(principal_location.latitude) if principal_location.latitude is not None else None,
                'long': float(principal_location.longitude) if principal_location.longitude is not None else None,
                'id': f"warehouse-{principal_location.id}",  # Para diferenciar de entregas
            })

        # Agora adiciona as paradas da rota ordenadas
        for rd in RouteDelivery.objects.filter(route=route).order_by('position'):
            stops.append({
                'client': rd.delivery.customer_name,
                'position': rd.position + 1 if principal_location else rd.position,  # Corrige a posição se tiver galpão
                'order_number': rd.delivery.order_number,
                'address': rd.delivery.full_address,
                'lat': float(rd.delivery.latitude) if rd.delivery.latitude is not None else None,
                'long': float(rd.delivery.longitude) if rd.delivery.longitude is not None else None,
                'id': rd.delivery.id,
                'is_check': 1 if rd.delivery.is_check else 0
            })

        routes_data.append({
            'name': route.name,
            'color': route.color,
            'geojson': json.dumps(route.geojson),
            'stops': stops,
            'distance_km': route.distance_km,
            'time_min': route.time_min,
            'stops_count': route.stops + (1 if principal_location else 0),
        })

    context = {
        'composition': composition,
        'routes':  routes_data,
        'routes_json': json.dumps(routes_data),
    }

    return render(request, 'pages/router_explore.html', context)


@login_required
def route_loading_view(request, task_id):
    result = AsyncResult(str(task_id))

    if result.state in ['SUCCESS', 'FAILURE']:
        messages.warning(request, "Essa tarefa já foi finalizada ou não existe mais.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return render(request, 'partials/loading/route_loading.html', {'task_id': task_id})