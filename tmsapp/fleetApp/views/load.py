# tmsapp/scriptApp/views.py
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from tmsapp.models import LoadPlan
from tmsapp.scriptApp.models import RouteCompositionDelivery

@login_required
def loadplan_drawer(request, plan_id):
    plan = get_object_or_404(
        LoadPlan.objects
        .select_related('route__route_area', 'vehicle', 'vehicle__driver'),
        pk=plan_id
    )
    # serializar plan (mesma estrutura anterior)…
    plan_data = {
        'id': plan.id,
        'code': plan.code,
        'status': plan.status,
        'planned_date': plan.planned_date.isoformat() if plan.planned_date else '',
        'vehicle': {
            'license_plate': plan.vehicle.license_plate,
            'type': plan.vehicle.get_vehicle_type,
            'driver': str(plan.vehicle.driver),
        },
        'totals': {
            'deliveries': plan.total_deliveries,
            'weight_kg': plan.formatted_total_weight_kg,
            'max_weight_kg': plan.formatted_max_weight_kg,
            'volume_m3': plan.formatted_total_volume_m3,
            'max_volume_m3': plan.formatted_max_volume_m3,
            'value': plan.formatted_total_value,
            'overloaded': plan.is_overloaded(),
        }
    }

    # paradas roteirizadas
    stops = []
    for rd in plan.route.routedelivery_set.select_related('delivery__customer').order_by('position'):
        d = rd.delivery
        stops.append({
            'position': rd.position,
            'order_number': d.order_number,
            'client': d.customer.full_name,
            'address': d.full_address,
        })

    # extras (sem load_plan na mesma composição)
    comp_rel = RouteCompositionDelivery.objects.filter(load_plan=plan).first()
    extras = []
    if comp_rel:
        comp = comp_rel.route_composition
        extras_qs = RouteCompositionDelivery.objects.filter(
            route_composition=comp,
            load_plan__isnull=True
        ).select_related('delivery__customer').order_by('sequence')

        for rcd in extras_qs:
            d = rcd.delivery
            extras.append({
                'sequence':     rcd.sequence,
                'order_number': d.order_number,
                'client':       d.customer.full_name,
                'address':      d.full_address,
            })

    html = render_to_string('pages/routes/loadplan_details.html', {
        'plan': plan_data,
        'stops': stops,
        'extras': extras,
    }, request=request)

    return JsonResponse({'html': html})
