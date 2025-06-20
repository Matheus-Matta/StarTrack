import json
import time as time_module
from collections import defaultdict
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.contrib.auth import get_user_model
from shapely.geometry import shape, Point

from tmsapp.models import (
    RouteArea, RouteComposition, RouteCompositionDelivery, RouteDelivery, Route,
    Vehicle, CompanyLocation, DeliveryStatus, Delivery
)
from tmsapp.fleetApp.models import LoadPlan

from tmsapp.action import get_geojson_by_ors
from djangonotify.utils import send_progress, send_notification
from djangonotify.models import TaskRecord

User = get_user_model()

def can_fit_delivery(vehicle, current_weight, current_volume, delivery):
    """
    Verifica se uma entrega cabe no veículo considerando peso e volume.
    """
    delivery_weight = delivery.total_weight_kg or Decimal('0')
    delivery_volume = delivery.total_volume_m3 or Decimal('0')
    return (
        current_weight + delivery_weight <= vehicle.max_weight_kg and
        current_volume + delivery_volume <= vehicle.max_volume_m3
    )

@shared_task(bind=True)
def create_script_perso_task(self, user_id, tkrecord_id, start_date, end_date):
    try:
        task_id = self.request.id
        tk = TaskRecord.objects.get(pk=tkrecord_id)
        tk.task_id = task_id
        tk.save(update_fields=['task_id'])
        time_module.sleep(5)
        user = User.objects.get(pk=user_id)

        send_progress(task_id, user_id, "Iniciando roteirização completa...", 1, status='progress')
        # Carrega entregas no período
        if start_date == end_date:
            qs = Delivery.objects.filter(created_at__date=start_date, status=DeliveryStatus.PENDING)
        else:
            qs = Delivery.objects.filter(created_at__date__range=[start_date, end_date], status=DeliveryStatus.PENDING)
        deliveries = list(qs.exclude(latitude__isnull=True, longitude__isnull=True))
        total_deliveries = len(deliveries)
        if total_deliveries == 0:
            send_notification(user_id, title="Roteirização",
                              message=f"0 entregas de {start_date} a {end_date}.", level="warning")
            send_progress(task_id, user_id, "Nenhuma entrega encontrada.", 100, status='success')
            return {"status": "no_deliveries", "count": 0}

        # Carrega áreas válidas
        send_progress(task_id, user_id, "Carregando áreas...", 10, status='progress')
        areas = []
        for area in RouteArea.objects.filter(is_active=True):
            if not area.geojson:
                continue
            try:
                polygon = shape(json.loads(area.geojson))
                areas.append((area, polygon))
            except Exception:
                send_notification(user_id, title='Área inválida',
                                  message=f'Área {area.name} sem polígono válido.', level='warning')
        if not areas:
            send_progress(task_id, user_id, "Nenhuma área válida.", 100, status='failure')
            return {"status": "no_areas", "count": 0}

        # Atribui cada entrega à área mais próxima (distância entre ponto e polígono)
        area_delivery_map = defaultdict(list)
        for d in deliveries:
            pt = Point(float(d.longitude), float(d.latitude))
            # encontra área mais próxima
            nearest_area, nearest_poly = min(areas, key=lambda ap: ap[1].distance(pt))
            dist = nearest_poly.distance(pt)
            area_delivery_map[nearest_area].append((d, dist))

        # Ordena entregas de cada área por distância crescente
        for area in list(area_delivery_map.keys()):
            area_delivery_map[area].sort(key=lambda tup: tup[1])
            # substitui tuplas por objetos de entrega
            area_delivery_map[area] = [d for d, _ in area_delivery_map[area]]

        # Cria composição de rota
        route_comp = RouteComposition.objects.create(
            name='Roteirização', start_date=start_date, end_date=end_date,
            created_by=user, is_active=True
        )
        route_comp.name = f'Roteirização RTR-{route_comp.pk}'
        route_comp.save()

        departure = CompanyLocation.objects.filter(is_principal=True, is_active=True).first()
        created_plans = []
        unassigned_global = []

        # Processa cada área separadamente
        send_progress(task_id, user_id, "Processando áreas e alocando cargas...", 20, status='progress')
        total_areas = len(area_delivery_map)
        for idx, (area, deliveries_sorted) in enumerate(area_delivery_map.items(), start=1):
            progress = int(20 + (idx / total_areas) * 60)
            send_progress(task_id, user_id,
                          f"Área {area.name}: {len(deliveries_sorted)} entregas...", progress, status='progress')
            # veículos desta área
            vehicles = list(Vehicle.objects.filter(route_area=area, is_active=True)
                            .order_by('-max_weight_kg', '-max_volume_m3'))
            if not vehicles:
                send_notification(user_id, title=f"Área {area.name}", message="Sem veículos nesta área.", level='warning')
                unassigned_global.extend(deliveries_sorted)
                continue

            # estruturas de carga por veículo
            vehicle_loads = {v.id: [] for v in vehicles}
            vehicle_weights = {v.id: Decimal('0') for v in vehicles}
            vehicle_volumes = {v.id: Decimal('0') for v in vehicles}

            # aloca entregas por ordem de proximidade
            unassigned = []
            for d in deliveries_sorted:
                placed = False
                for veh in vehicles:
                    vid = veh.id
                    if can_fit_delivery(veh, vehicle_weights[vid], vehicle_volumes[vid], d):
                        vehicle_loads[vid].append(d)
                        vehicle_weights[vid] += d.total_weight_kg or Decimal('0')
                        vehicle_volumes[vid] += d.total_volume_m3 or Decimal('0')
                        placed = True
                        break
                if not placed:
                    unassigned.append(d)
            unassigned_global.extend(unassigned)

            # cria LoadPlan e rota para cada veículo
            for vid, del_list in vehicle_loads.items():
                if not del_list:
                    continue
                veh = Vehicle.objects.get(pk=vid)
                temp_route = Route.objects.create(
                    name=f"Temp {area.name}-{veh.name}", route_area=area,
                    stops=len(del_list), distance_km=0, time_min=0,
                    geojson={}, points=[], created_by=user
                )
                lp = LoadPlan.objects.create(
                    name=f"Carga {area.name}", route=temp_route,
                    vehicle=veh, planned_date=start_date,
                    max_weight_kg=veh.max_weight_kg, max_volume_m3=veh.max_volume_m3,
                    status='draft', created_by=user
                )
                route_comp.load_plans_direct.add(lp)
                # sequencia e otimização
                for seq, d in enumerate(del_list, start=1):
                    RouteCompositionDelivery.objects.update_or_create(
                        route_composition=route_comp, delivery=d,
                        defaults={'load_plan': lp, 'sequence': seq, 'route_area': area}
                    )
                coords = [{'lat': float(d.latitude), 'long': float(d.longitude), 'order_number': d.order_number}
                          for d in del_list]
                try:
                    geo, dur, dist, ord_del = get_geojson_by_ors(coords, departure)
                    temp_route.name = f"Rota {area.name}-{veh.name}-{start_date}"
                    temp_route.distance_km = dist / 1000
                    temp_route.time_min = dur / 60
                    temp_route.geojson = geo
                    temp_route.points = coords
                    temp_route.save()
                    for pos, od in enumerate(ord_del, start=1):
                        d_obj = Delivery.objects.get(order_number=od['order_number'])
                        RouteDelivery.objects.create(route=temp_route, delivery=d_obj, position=pos)
                    created_plans.append({'area': area.name, 'vehicle': veh.name, 'deliveries': len(del_list)})
                except Exception as e:
                    send_notification(user_id, title=f"Erro otimização {area.name}", message=str(e), level="error")
                    created_plans.append({'area': area.name, 'vehicle': veh.name, 'deliveries': len(del_list), 'error': str(e)})

        # registra globalmente não alocadas
        for d in unassigned_global:
            RouteCompositionDelivery.objects.update_or_create(
                route_composition=route_comp, delivery=d,
                defaults={'load_plan': None, 'sequence': 0, 'route_area': None}
            )

        # finaliza
        send_progress(task_id, user_id, "Roteirização concluída!", 100, status='success')
        route_comp._sync_on_status_change('draft')
        total_plans = len(created_plans)
        total_del = sum(p['deliveries'] for p in created_plans)
        summary = f"• {total_plans} planos criados • {total_del} entregas processadas • {len(unassigned_global)} não alocadas"
        send_notification(user_id, title="Roteirização Concluída", message=summary, level="success")
        return {"status": "success", "detalhes": summary}

    except Exception as e:
        send_progress(self.request.id, user_id, f"Erro: {str(e)}", 100, status='failure')
        send_notification(user_id, title="Erro na Roteirização", message=str(e), level="error")
        return {"status": "error", "error": str(e)}
