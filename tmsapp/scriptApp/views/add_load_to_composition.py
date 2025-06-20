# tmsapp/scriptApp/views.py

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from tmsapp.models import RouteComposition
from tmsapp.fleetApp.models import LoadPlan
from tmsapp.models import Vehicle, Route


@login_required
@require_POST
def add_load_to_composition(request, scripting_id):
    """
    Adiciona um novo LoadPlan a uma RouteComposition, desde que o veículo
    ainda não tenha carga nessa composição. Espera receber no POST:
      - vehicle_id: ID do Vehicle a ser usado na nova carga.
    """

    composition = get_object_or_404(RouteComposition, pk=scripting_id)

    # Obter o vehicle_id do formulário
    vehicle_ids = request.POST.getlist('vehicle_ids')

    if not vehicle_ids:
        messages.error(request, "Você deve informar o veículo para criar a nova carga.")
        return redirect('tmsapp:scriptapp:scripting_view', scripting_id)
    
    criados = []
    ignorados = []
    for vid in vehicle_ids:
        try:
            vehicle = Vehicle.objects.get(pk=vid)
        except Vehicle.DoesNotExist:
            # Se alguém mexeu no front e enviou ID inválido, pula
            continue

        # Verifica se já existe carga para esse veículo nessa composição
        if composition.load_plans_direct.filter(vehicle=vehicle).exists():
            ignorados.append(vehicle.license_plate)
            continue
        
        area = vehicle.route_area
        rt = Route.objects.create(
                name=f"Rota {area.name} - {vehicle.name}",
                route_area=area,
                stops=0,
                distance_km=0,
                time_min=0,
                geojson={},
                points=[],
                created_by=request.user
            )
        
        # Se ainda não existe, cria um novo LoadPlan sem rota definida
        new_load_name = f"Carga {area.name}"
        load_plan = LoadPlan.objects.create(
            name=new_load_name,
            route=rt,
            vehicle=vehicle,
            planned_date=timezone.now().date(),
            max_weight_kg=vehicle.max_weight_kg,
            max_volume_m3=vehicle.max_volume_m3,
            created_by=request.user
        )
        composition.load_plans_direct.add(load_plan)
        criados.append(vehicle.license_plate)

    if criados:
        messages.success(
            request,
            f"Cargas criadas para veículo(s): {', '.join(criados)}."
        )
    if ignorados:
        messages.warning(
            request,
            f"Veículo(s) ignorado(s) (já tinham carga): {', '.join(ignorados)}."
        )
        
    return redirect('tmsapp:scriptapp:scripting_view', scripting_id)
