import json
import time as time_module
import requests
from datetime import datetime, date, time
from collections import defaultdict
from decimal import Decimal

from asgiref.sync import async_to_sync
from celery import shared_task
from django.db import transaction
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from django.utils import timezone

from shapely.geometry import shape, Point

from tmsapp.models import (
    RouteArea, RouteComposition, RouteCompositionDelivery, RouteDelivery, Route, 
    LoadPlan, Vehicle, CompanyLocation
)
from tmsapp.action import get_geojson_by_ors
from tmsapp.models import Delivery

from djangonotify.utils import send_progress, send_notification
from djangonotify.models import TaskRecord

User = get_user_model()

def can_fit_delivery(vehicle, current_weight, current_volume, delivery):
    """
    Verifica se uma entrega cabe no veículo
    """
    delivery_weight = delivery.total_weight_kg or Decimal('0.000')
    delivery_volume = delivery.total_volume_m3 or Decimal('0.000')
    
    return (
        current_weight + delivery_weight <= vehicle.max_weight_kg and
        current_volume + delivery_volume <= vehicle.max_volume_m3
    )


def distribute_deliveries_to_vehicles(deliveries, vehicles):
    """
    Distribui entregas entre veículos otimizando capacidade
    
    Returns:
        dict: {vehicle_id: [deliveries]}
    """
    # Ordena entregas por peso/volume (maiores primeiro)
    sorted_deliveries = sorted(
        deliveries,
        key=lambda d: (d.total_weight_kg or Decimal('0')) + (d.total_volume_m3 or Decimal('0')),
        reverse=True
    )
    
    # Ordena veículos por capacidade (maiores primeiro)
    sorted_vehicles = sorted(
        vehicles,
        key=lambda v: v.max_weight_kg + v.max_volume_m3,
        reverse=True
    )
    
    vehicle_loads = {}
    vehicle_weights = {}
    vehicle_volumes = {}
    
    # Inicializa tracking de capacidades
    for vehicle in sorted_vehicles:
        vehicle_loads[vehicle.id] = []
        vehicle_weights[vehicle.id] = Decimal('0.000')
        vehicle_volumes[vehicle.id] = Decimal('0.000')
    
    # Distribui entregas
    for delivery in sorted_deliveries:
        placed = False
        
        # Tenta colocar no primeiro veículo que couber
        for vehicle in sorted_vehicles:
            if can_fit_delivery(
                vehicle,
                vehicle_weights[vehicle.id],
                vehicle_volumes[vehicle.id],
                delivery
            ):
                vehicle_loads[vehicle.id].append(delivery)
                vehicle_weights[vehicle.id] += delivery.total_weight_kg or Decimal('0.000')
                vehicle_volumes[vehicle.id] += delivery.total_volume_m3 or Decimal('0.000')
                placed = True
                break
        
        if not placed:
            # Se não couber em nenhum veículo, coloca no primeiro (sobrecarga)
            first_vehicle = sorted_vehicles[0]
            vehicle_loads[first_vehicle.id].append(delivery)
            vehicle_weights[first_vehicle.id] += delivery.total_weight_kg or Decimal('0.000')
            vehicle_volumes[first_vehicle.id] += delivery.total_volume_m3 or Decimal('0.000')
    
    return vehicle_loads


@shared_task(bind=True)
def create_script_perso_task(self, user_id, tkrecord_id, start_date, end_date):
    try:
        task_id = self.request.id
        tk = TaskRecord.objects.get(pk=tkrecord_id)
        tk.task_id = task_id
        tk.save(update_fields=['task_id'])
        
        user = User.objects.get(pk=user_id)
        
        send_progress(task_id, user_id, "Iniciando roteirização completa...", 1, status='progress')
        
        # 1. FILTRAR ENTREGAS
        send_progress(task_id, user_id, f"Carregando entregas entre {start_date} e {end_date}...", 5, status='progress')
        
        if start_date == end_date:
            deliveries = Delivery.objects.filter(
                created_at__date=start_date
            ).exclude(latitude__isnull=True, longitude__isnull=True)
        else:
            deliveries = Delivery.objects.filter(
                created_at__date__range=[start_date, end_date]
            ).exclude(latitude__isnull=True, longitude__isnull=True)
        
        if not deliveries.exists():
            send_notification(
                user_id,
                title="Roteirização",
                message=f"Nenhuma entrega encontrada de {start_date} a {end_date}.",
                level="warning"
            )
            send_progress(task_id, user_id, "Nenhuma entrega encontrada.", 100, status='success')
            return {"status": "no_deliveries", "count": 0}
        
        # 2. CARREGAR ÁREAS E AGRUPAR ENTREGAS
        send_progress(task_id, user_id, "Agrupando entregas por área...", 10, status='progress')
        
        areas = []
        for area in RouteArea.objects.filter(is_active=True):
            try:
                if area.geojson:
                    geo = json.loads(area.geojson)
                    polygon = shape(geo)
                    areas.append((area, polygon))
            except Exception:
                send_notification(user_id,
                    title='Área de rota inválida',
                    message=f'{area.name} não possui um polígono válido',
                    level='warning'
                )
                continue

        # Agrupa entregas por área
        area_groups = defaultdict(list)
        extras = []
        
        for d in deliveries:
            pt = Point(float(d.longitude), float(d.latitude))
            found = False
            for area, polygon in areas:
                if polygon.contains(pt):
                    area_groups[area].append(d)
                    found = True
                    break
            if not found:
                extras.append(d)

        # Atribui extras à área mais próxima
        for d in extras:
            pt = Point(float(d.longitude), float(d.latitude))
            if areas:  # Verifica se há áreas disponíveis
                nearest_area, _ = min(areas, key=lambda ap: ap[1].distance(pt))
                area_groups[nearest_area].append(d)

        if not area_groups:
            send_notification(user_id,
                title="Roteirização",
                message="Nenhuma área de rota válida encontrada.",
                level="warning"
            )
            return {"status": "no_areas", "count": 0}

        # 3. PROCESSAR CADA ÁREA
        send_progress(task_id, user_id, "Processando áreas e criando cargas...", 20, status='progress')
        
        total_areas = len(area_groups)
        processed_areas = 0
        created_plans = []
        
        # Busca ponto de partida principal
        departure_location = CompanyLocation.objects.filter(
            is_principal=True, is_active=True
        ).first()
        
        if not departure_location:
            send_notification(user_id,
                title="Roteirização",
                message="Nenhum local principal definido. Usando primeira entrega como origem.",
                level="warning"
            )

        with transaction.atomic():
            # Cria RouteComposition
            composition_name = f"Rota {area.name} - {vehicle.name} - {start_date}"
            route_composition = RouteComposition.objects.create(
                name=composition_name,
                created_by=user,
                is_active=True
            )
            route_composition.save()
            for area, area_deliveries in area_groups.items():
                processed_areas += 1
                progress = 20 + (processed_areas / total_areas) * 60
                
                send_progress(task_id, user_id, 
                    f"Processando área {area.name} ({len(area_deliveries)} entregas)...", 
                    int(progress), status='progress')
                
                # Busca veículos da área
                vehicles = Vehicle.objects.filter(
                    route_area=area, 
                    is_active=True
                ).order_by('-capacity_weight', '-capacity_volume')
                
                if not vehicles.exists():
                    send_notification(user_id,
                        title=f"Área {area.name}",
                        message="Nenhum veículo disponível nesta área.",
                        level="warning"
                    )
                    continue
                
                # Distribui entregas entre veículos
                vehicle_distributions = distribute_deliveries_to_vehicles(
                    area_deliveries, vehicles
                )
                
                # Cria LoadPlans e Rotas para cada veículo com entregas
                for vehicle_id, vehicle_deliveries in vehicle_distributions.items():
                    if not vehicle_deliveries:
                        continue
                    
                    vehicle = Vehicle.objects.get(id=vehicle_id)
                    
                    # Cria LoadPlan
                    load_plan_name = f"Carga {area.name} - {vehicle.name} - {start_date}"
                    
                    # Cria rota temporária (será atualizada depois)
                    temp_route = Route.objects.create(
                        name=f"Temp Route {area.name} - {vehicle.name}",
                        route_area=area,
                        stops=len(vehicle_deliveries),
                        distance_km=0,
                        time_min=0,
                        geojson={},
                        points=[],
                        created_by=user
                    )
                    
                    load_plan = LoadPlan.objects.create(
                        name=load_plan_name,
                        route=temp_route,
                        vehicle=vehicle,
                        planned_date=start_date,
                        status='planned',
                        created_by=user
                    )
                    
                    # Adiciona entregas à composição
                    for idx, delivery in enumerate(vehicle_deliveries):
                        RouteCompositionDelivery.objects.create(
                            route_composition=route_composition,
                            delivery=delivery,
                            load_plan=load_plan,
                            sequence=idx + 1
                        )
                    
                    # Prepara coordenadas para otimização
                    coordinates = []
                    for delivery in vehicle_deliveries:
                        coordinates.append({
                            'lat': float(delivery.latitude),
                            'long': float(delivery.longitude),
                            'order_number': delivery.order_number
                        })
                    
                    try:
                        # Otimiza rota com VROOM/ORS
                        geojson, duration, distance, ordered_deliveries = get_geojson_by_ors(
                            coordinates, departure_location
                        )
                        
                        # Atualiza rota com dados otimizados
                        temp_route.name = f"Rota {area.name} - {vehicle.name} - {start_date}"
                        temp_route.distance_km = distance / 1000  # converte metros para km
                        temp_route.time_min = duration / 60  # converte segundos para minutos
                        temp_route.geojson = geojson
                        temp_route.points = coordinates
                        temp_route.save()
                        
                        # Cria RouteDelivery com ordem otimizada
                        for idx, ordered_delivery in enumerate(ordered_deliveries):
                            delivery = Delivery.objects.get(
                                order_number=ordered_delivery['order_number']
                            )
                            RouteDelivery.objects.create(
                                route=temp_route,
                                delivery=delivery,
                                position=idx + 1
                            )
                        
                        # Recalcula totais do LoadPlan
                        load_plan.calculate_totals()
                        
                        created_plans.append({
                            'area': area.name,
                            'vehicle': vehicle.name,
                            'deliveries': len(vehicle_deliveries),
                            'load_plan_id': load_plan.id,
                            'route_id': temp_route.id,
                            'distance_km': round(distance / 1000, 2),
                            'duration_min': round(duration / 60, 1),
                            'overloaded': load_plan.is_overloaded()
                        })
                        
                    except Exception as e:
                        send_notification(user_id,
                            title=f"Erro na otimização - {area.name}",
                            message=f"Erro ao otimizar rota para {vehicle.name}: {str(e)}",
                            level="error"
                        )
                        # Mantém rota sem otimização
                        load_plan.calculate_totals()
                        
                        created_plans.append({
                            'area': area.name,
                            'vehicle': vehicle.name,
                            'deliveries': len(vehicle_deliveries),
                            'load_plan_id': load_plan.id,
                            'route_id': temp_route.id,
                            'distance_km': 0,
                            'duration_min': 0,
                            'overloaded': load_plan.is_overloaded(),
                            'error': 'Otimização falhou'
                        })
        
        # 4. FINALIZAÇÃO
        send_progress(task_id, user_id, "Roteirização concluída!", 100, status='success')
        
        # Notificação de resumo
        total_plans = len(created_plans)
        overloaded_plans = sum(1 for p in created_plans if p.get('overloaded', False))
        
        summary_message = f"""
        Roteirização concluída:
        • {total_plans} planos de carga criados
        • {sum(p['deliveries'] for p in created_plans)} entregas processadas
        • {overloaded_plans} veículos com sobrecarga
        """
        
        send_notification(user_id,
            title="Roteirização Concluída",
            message=summary_message,
            level="success"
        )
        
        return {
            "status": "success",
            "total_deliveries": deliveries.count(),
            "total_areas": total_areas,
            "created_plans": created_plans,
            "overloaded_plans": overloaded_plans
        }
        
    except Exception as e:
        send_progress(task_id, user_id, f"Erro na roteirização: {str(e)}", 100, status='failure')
        send_notification(user_id,
            title="Erro na Roteirização",
            message=f"Falha no processamento: {str(e)}",
            level="error"
        )
        return {
            "status": "error",
            "error": str(e)
        }