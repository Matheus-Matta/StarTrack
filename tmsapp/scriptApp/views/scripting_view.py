from tmsapp.models import RouteComposition, Vehicle
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from celery.result import AsyncResult
from django.contrib import messages
import json

@login_required
def scripting_view(request, scripting_id):
    # Busca a composição de rotas ou 404
    scripting = get_object_or_404(RouteComposition, pk=scripting_id)

    # Obter todos os IDs de veículos que já têm LoadPlan nessa composição
    usados = scripting.load_plans_direct.values_list('vehicle_id', flat=True)

    # Filtrar apenas veículos ativos que ainda não estejam nessa composição
    available_vehicles = Vehicle.objects.filter(is_active=True).exclude(pk__in=usados)
    
    return render(request, 'pages/routes/scripting_view.html', {
        'scripting': scripting,
        'available_vehicles': available_vehicles,
    })


@login_required
def route_loading_view(request, task_id):
    result = AsyncResult(str(task_id))

    if result.state in ['SUCCESS', 'FAILURE']:
        messages.warning(request, "Essa tarefa já foi finalizada ou não existe mais.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return render(request, 'partials/loading/route_loading.html', {'task_id': task_id})