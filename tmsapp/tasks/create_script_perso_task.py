import json
import time as time_module
from collections import defaultdict
from decimal import Decimal
import math

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

from django.urls import reverse
from django.conf import settings

User = get_user_model()

class RoutePlanner:
    """
    Planejador de rotas otimizado que:
    - Processa áreas por proximidade do ponto de saída
    - Completa carga de veículos com entregas de múltiplas áreas
    - Evita desperdício de capacidade
    - Garante apenas UM LoadPlan por veículo
    """
    
    def __init__(self, task, user_id, tkrecord_id, vehicles_areas, start_date, end_date):
        self.task = task
        self.task_id = task.request.id
        self.user_id = user_id
        self.tkrecord_id = tkrecord_id
        self.vehicles_areas = self._parse_custom_config(vehicles_areas)
        self.start_date = start_date
        self.end_date = end_date
        self.user = User.objects.get(pk=user_id)
        self.route_comp = None
        self.departure = CompanyLocation.objects.filter(is_principal=True, is_active=True).first()
        self.area_delivery_map = defaultdict(list)
        self.created_plans = []
        self.unassigned_global = []
        self.processed_deliveries = set()
        
        # CORREÇÃO: Controle de veículos para evitar múltiplos LoadPlans
        self.vehicle_loads = {}  # {vehicle_id: {'deliveries': [...], 'areas': set(), 'main_area': area}}
        self.vehicle_load_plans = {}  # {vehicle_id: LoadPlan} - para controle de unicidade

    def _update_task_record(self):
        """Atualiza o registro TaskRecord com o ID da task"""
        tk = TaskRecord.objects.get(pk=self.tkrecord_id)
        tk.task_id = self.task_id
        tk.save(update_fields=['task_id'])

    def _send_progress(self, message, percent, status='progress'):
        """Envia progresso da task para o usuário"""
        send_progress(self.task_id, self.user_id, message, percent, status=status)

    def _notify(self, title, message, level):
        """Envia notificação para o usuário"""
        send_notification(self.user_id, title=title, message=message, level=level)

    def _parse_custom_config(self, vehicles_areas):
        """Converte configuração customizada em dict válido"""
        if vehicles_areas and isinstance(vehicles_areas, str):
            try:
                return json.loads(vehicles_areas)
            except json.JSONDecodeError:
                self._notify("Erro", "Formato inválido de vehicles_areas.", "error")
        return vehicles_areas or {}

    def _calculate_distance_to_departure(self, area):
        """Calcula distância aproximada entre área e ponto de saída"""
        if not self.departure or not area.geojson:
            return float('inf')
        
        try:
            area_geom = shape(json.loads(area.geojson))
            area_center = area_geom.centroid
            
            # Cálculo de distância aproximada usando fórmula haversine
            lat1, lon1 = float(self.departure.latitude), float(self.departure.longitude)
            lat2, lon2 = area_center.y, area_center.x
            
            return self._haversine_distance(lat1, lon1, lat2, lon2)
        except Exception:
            return float('inf')

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calcula distância haversine entre dois pontos"""
        R = 6371  # Raio da Terra em km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    def _get_vehicle_remaining_capacity(self, vehicle):
        """Calcula capacidade restante do veículo"""
        if vehicle.id not in self.vehicle_loads:
            return {
                'weight': vehicle.max_weight_kg or Decimal('0'),
                'volume': vehicle.max_volume_m3 or Decimal('0')
            }
        
        current_deliveries = self.vehicle_loads[vehicle.id]['deliveries']
        used_weight = sum(d.total_weight_kg or Decimal('0') for d in current_deliveries)
        used_volume = sum(d.total_volume_m3 or Decimal('0') for d in current_deliveries)
        
        return {
            'weight': (vehicle.max_weight_kg or Decimal('0')) - used_weight,
            'volume': (vehicle.max_volume_m3 or Decimal('0')) - used_volume
        }

    def _can_add_delivery_to_vehicle(self, vehicle, delivery):
        """Verifica se entrega pode ser adicionada ao veículo"""
        remaining = self._get_vehicle_remaining_capacity(vehicle)
        delivery_weight = delivery.total_weight_kg or Decimal('0')
        delivery_volume = delivery.total_volume_m3 or Decimal('0')
        
        return (delivery_weight <= remaining['weight'] and 
                delivery_volume <= remaining['volume'])

    def _add_delivery_to_vehicle(self, vehicle, delivery, area):
        """Adiciona entrega ao veículo"""
        if vehicle.id not in self.vehicle_loads:
            self.vehicle_loads[vehicle.id] = {
                'deliveries': [],
                'areas': set(),
                'main_area': area,
                'vehicle': vehicle
            }
        
        self.vehicle_loads[vehicle.id]['deliveries'].append(delivery)
        self.vehicle_loads[vehicle.id]['areas'].add(area)
        self.processed_deliveries.add(delivery.id)

    def load_deliveries(self):
        """Carrega entregas pendentes no período especificado"""
        self._send_progress("Iniciando roteirização completa...", 1)
        
        if self.start_date == self.end_date:
            qs = Delivery.objects.filter(
                date_delivery=self.start_date, 
                status=DeliveryStatus.PENDING
            )
        else:
            qs = Delivery.objects.filter(
                date_delivery__range=[self.start_date, self.end_date],
                status=DeliveryStatus.PENDING
            )
        
        deliveries = list(qs.exclude(latitude__isnull=True, longitude__isnull=True))
        
        if not deliveries:
            self._notify("Roteirização", 
                        f"0 entregas de {self.start_date} a {self.end_date}.", 
                        "warning")
            self._send_progress("Nenhuma entrega encontrada.", 100, status='success')
            return False
        
        self.deliveries = deliveries
        return True

    def load_areas(self):
        """Carrega áreas ativas e ordena por proximidade do ponto de saída"""
        self._send_progress("Carregando áreas...", 10)
        
        areas = []
        for area in RouteArea.objects.filter(is_active=True):
            if not area.geojson:
                continue
            try:
                poly = shape(json.loads(area.geojson))
                distance = self._calculate_distance_to_departure(area)
                areas.append((area, poly, distance))
            except Exception:
                self._notify('Área inválida', 
                           f'Área {area.name} sem polígono válido.', 
                           'warning')
        
        if not areas:
            self._send_progress("Nenhuma área válida.", 100, status='failure')
            return False
        
        # Ordena por proximidade do ponto de saída
        areas.sort(key=lambda x: x[2])
        self.areas = [(area, poly) for area, poly, _ in areas]
        return True

    def assign_deliveries(self):
        """Atribui entregas às áreas mais próximas"""
        self._send_progress("Atribuindo entregas às áreas...", 15)
        
        for delivery in self.deliveries:
            pt = Point(float(delivery.longitude), float(delivery.latitude))
            nearest_area, nearest_poly = min(
                self.areas, key=lambda ap: ap[1].distance(pt)
            )
            self.area_delivery_map[nearest_area].append(
                (delivery, nearest_poly.distance(pt))
            )
        
        # Ordena entregas por proximidade dentro de cada área
        for area, tuples in self.area_delivery_map.items():
            tuples.sort(key=lambda x: x[1])
            self.area_delivery_map[area] = [d for d, _ in tuples]

    def build_composition(self):
        """Cria composição de rota para armazenar resultados"""
        self.route_comp = RouteComposition.objects.create(
            name='Roteirização', 
            start_date=self.start_date,
            end_date=self.end_date, 
            created_by=self.user, 
            is_active=True
        )
        self.route_comp.name = f'Roteirização RTR-{self.route_comp.pk}'
        self.route_comp.save()

    def process_vehicle_config(self):
        """Processa configuração de veículos (customizada ou padrão)"""
        if self.vehicles_areas:
            return self._process_custom_config()
        return self._process_default_config()

    def _process_custom_config(self):
        """
        Processa configuração customizada com otimização de carga:
        1. Ordena áreas por proximidade
        2. Completa carga de veículos com entregas de múltiplas áreas
        """
        self._send_progress("Usando configuração customizada...", 20)
        
        # Mapeia veículos para suas áreas
        vehicle_areas = self._build_vehicle_areas_map()
        if not vehicle_areas:
            return
        
        # Cria mapa de áreas para veículos
        area_vehicles_map = defaultdict(list)
        for vehicle, areas in vehicle_areas.items():
            for area in areas:
                area_vehicles_map[area].append(vehicle)
        
        # Processa áreas ordenadas por proximidade
        ordered_areas = [area for area, _ in self.areas if area in area_vehicles_map]
        
        self._process_areas_with_vehicle_optimization(ordered_areas, area_vehicles_map)

    def _build_vehicle_areas_map(self):
        """Constrói mapa de veículos para áreas válidas"""
        vehicle_areas = {}
        
        for vid, area_ids in self.vehicles_areas.items():
            try:
                veh = Vehicle.objects.get(pk=int(vid), is_active=True)
            except Vehicle.DoesNotExist:
                self._notify("Veículo não encontrado", 
                           f"Veículo ID {vid} não encontrado.", 'warning')
                continue
            
            valid_areas = []
            for aid in area_ids:
                try:
                    area = RouteArea.objects.get(pk=int(aid), is_active=True)
                    valid_areas.append(area)
                except RouteArea.DoesNotExist:
                    self._notify("Área não encontrada", 
                               f"Área ID {aid} não encontrada.", 'warning')
            
            if valid_areas:
                vehicle_areas[veh] = valid_areas
        
        if not vehicle_areas:
            self._notify("Erro", "Nenhum veículo/área válido encontrado.", 'error')
            self._send_progress("Nenhuma configuração válida.", 100, status='failure')
        
        return vehicle_areas

    def _process_areas_with_vehicle_optimization(self, ordered_areas, area_vehicles_map):
        """
        Processa áreas com otimização de carga:
        Veículos completam sua carga com entregas de múltiplas áreas
        """
        total_areas = len(ordered_areas)
        
        for idx, area in enumerate(ordered_areas, 1):
            pct = int(20 + idx/total_areas*60)
            available_deliveries = self._get_available_deliveries_for_area(area)
            
            if not available_deliveries:
                continue
                
            self._send_progress(f"Área {area.name}: {len(available_deliveries)} entregas...", pct)
            
            # Pega veículos desta área ordenados por capacidade restante
            vehicles = self._get_ordered_vehicles_for_area(area, area_vehicles_map)
            
            # Tenta alocar entregas nos veículos
            self._allocate_deliveries_to_vehicles(area, vehicles, available_deliveries)
            
            # Completa carga dos veículos com entregas de outras áreas
            self._complete_vehicle_loads(vehicles)

    def _get_available_deliveries_for_area(self, area):
        """Retorna entregas disponíveis (não processadas) para uma área"""
        return [
            d for d in self.area_delivery_map.get(area, [])
            if d.id not in self.processed_deliveries
        ]

    def _get_ordered_vehicles_for_area(self, area, area_vehicles_map):
        """Retorna veículos ordenados por capacidade restante (maior primeiro)"""
        vehicles = area_vehicles_map.get(area, [])
        
        # Ordena por capacidade restante (peso + volume)
        def vehicle_priority(vehicle):
            remaining = self._get_vehicle_remaining_capacity(vehicle)
            return (remaining['weight'] + remaining['volume'], 
                    vehicle.max_weight_kg or Decimal('0'))
        
        return sorted(vehicles, key=vehicle_priority, reverse=True)

    def _allocate_deliveries_to_vehicles(self, area, vehicles, deliveries):
        """Aloca entregas aos veículos respeitando capacidades"""
        remaining_deliveries = deliveries.copy()
        
        for vehicle in vehicles:
            if not remaining_deliveries:
                break
            
            # Carrega o máximo possível neste veículo
            allocated = []
            for delivery in remaining_deliveries[:]:
                if self._can_add_delivery_to_vehicle(vehicle, delivery):
                    self._add_delivery_to_vehicle(vehicle, delivery, area)
                    allocated.append(delivery)
                    remaining_deliveries.remove(delivery)
            
            if allocated:
                self._send_progress(
                    f"Veículo {vehicle.name}: +{len(allocated)} entregas", 
                    None
                )
        
        # Entregas não alocadas ficam para próximas tentativas
        self.unassigned_global.extend(remaining_deliveries)

    def _complete_vehicle_loads(self, vehicles):
        """
        Completa carga dos veículos com entregas de outras áreas
        """
        for vehicle in vehicles:
            if vehicle.id not in self.vehicle_loads:
                continue
            
            # Tenta completar carga com entregas de outras áreas
            for other_area, other_deliveries in self.area_delivery_map.items():
                if not other_deliveries:
                    continue
                
                available_deliveries = [
                    d for d in other_deliveries
                    if d.id not in self.processed_deliveries
                ]
                
                for delivery in available_deliveries[:]:
                    if self._can_add_delivery_to_vehicle(vehicle, delivery):
                        self._add_delivery_to_vehicle(vehicle, delivery, other_area)
                        self.unassigned_global = [
                            d for d in self.unassigned_global 
                            if d.id != delivery.id
                        ]

    def _process_default_config(self):
        """Processa configuração padrão usando route_area dos veículos"""
        self._send_progress("Usando configuração padrão...", 20)
        
        # Processa áreas ordenadas por proximidade
        total = len(self.area_delivery_map)
        for idx, (area, deliveries) in enumerate(self.area_delivery_map.items(), 1):
            pct = int(20 + idx/total*60)
            self._send_progress(f"Área {area.name}: {len(deliveries)} entregas...", pct)
            
            vehicles = list(Vehicle.objects.filter(route_area=area, is_active=True)
                           .order_by('-max_weight_kg', '-max_volume_m3'))
            
            if not vehicles:
                self._notify(f"Área {area.name}", "Sem veículos nesta área.", 'warning')
                self.unassigned_global.extend(deliveries)
                continue
            
            # CORREÇÃO: Processa TODAS as entregas da área
            remaining_deliveries = deliveries.copy()
            
            # Tenta alocar todas as entregas nos veículos disponíveis
            for vehicle in vehicles:
                if not remaining_deliveries:
                    break  # Todas as entregas foram processadas
                
                # Aloca entregas para este veículo
                allocated_deliveries = []
                for delivery in remaining_deliveries[:]:
                    if self._can_add_delivery_to_vehicle(vehicle, delivery):
                        self._add_delivery_to_vehicle(vehicle, delivery, area)
                        allocated_deliveries.append(delivery)
                        remaining_deliveries.remove(delivery)
                
                # Log do progresso
                if allocated_deliveries:
                    self._send_progress(
                        f"Veículo {vehicle.name}: {len(allocated_deliveries)} entregas alocadas", 
                        None
                    )
            
            # Entregas que não couberam em nenhum veículo vão para não alocadas
            if remaining_deliveries:
                self.unassigned_global.extend(remaining_deliveries)
                self._send_progress(
                    f"Área {area.name}: {len(remaining_deliveries)} entregas não alocadas", 
                    None
                )

    def _create_single_load_plan_for_vehicle(self, vehicle_id, vehicle_data):
        """
        CORREÇÃO: Cria apenas UM LoadPlan por veículo
        """
        if vehicle_id in self.vehicle_load_plans:
            # Já existe LoadPlan para este veículo, pula
            return self.vehicle_load_plans[vehicle_id]
        
        vehicle = vehicle_data['vehicle']
        deliveries = vehicle_data['deliveries']
        main_area = vehicle_data['main_area']
        
        if not deliveries:
            return None
        
        # Cria rota única para o veículo
        route = Route.objects.create(
            name=f"RT-{vehicle.name}",
            route_area=main_area,
            stops=len(deliveries),
            distance_km=0,
            time_min=0,
            geojson={},
            points=[],
            created_by=self.user
        )
        
        # Cria LoadPlan único para o veículo
        plan = LoadPlan.objects.create(
            name=f"Carga {vehicle.name}",
            route=route,
            vehicle=vehicle,
            planned_date=self.start_date,
            max_weight_kg=vehicle.max_weight_kg,
            max_volume_m3=vehicle.max_volume_m3,
            status='draft',
            created_by=self.user
        )
        
        # Registra para evitar duplicação
        self.vehicle_load_plans[vehicle_id] = plan
        
        # Adiciona à composição
        self.route_comp.load_plans_direct.add(plan)
        
        # Cria registros de composição para todas as entregas
        for seq, delivery in enumerate(deliveries, 1):
            RouteCompositionDelivery.objects.update_or_create(
                route_composition=self.route_comp,
                delivery=delivery,
                defaults={
                    'load_plan': plan,
                    'sequence': seq,
                    'route_area': main_area
                }
            )
        
        # Otimiza rota
        self._optimize_route(route, deliveries, vehicle)
        
        return plan

    def _optimize_route(self, route, deliveries, vehicle):
        """Otimiza rota usando serviço ORS"""
        coords = [
            {
                'lat': float(d.latitude),
                'long': float(d.longitude),
                'order_number': d.order_number
            }
            for d in deliveries
        ]
        
        try:
            geo, dur, dist, ord_del = get_geojson_by_ors(coords, self.departure)
            
            # Atualiza rota
            route.name = f"RT-{route.id}"
            route.distance_km = dist / 1000
            route.time_min = dur / 60
            route.geojson = geo
            route.points = coords
            route.save()
            
            # Cria entregas da rota
            for pos, od in enumerate(ord_del, start=1):
                delivery_obj = Delivery.objects.get(order_number=od['order_number'])
                RouteDelivery.objects.create(
                    route=route,
                    delivery=delivery_obj,
                    position=pos
                )
            
            self.created_plans.append({
                'vehicle': vehicle.name,
                'area': route.route_area.name,
                'deliveries': len(deliveries)
            })
            
        except Exception as e:
            self._notify(f"Erro otimização {vehicle.name}", str(e), 'error')
            self.created_plans.append({
                'vehicle': vehicle.name,
                'area': route.route_area.name,
                'error': str(e)
            })

    def finalize(self):
        """Finaliza roteirização e gera relatório"""
        self._send_progress("Finalizando roteirização...", 90)
        
        # CORREÇÃO: Cria apenas UM LoadPlan por veículo
        for vehicle_id, vehicle_data in self.vehicle_loads.items():
            self._create_single_load_plan_for_vehicle(vehicle_id, vehicle_data)
        
        # Registra entregas não alocadas
        for delivery in self.unassigned_global:
            if delivery.id not in self.processed_deliveries:
                RouteCompositionDelivery.objects.update_or_create(
                    route_composition=self.route_comp,
                    delivery=delivery,
                    defaults={
                        'load_plan': None,
                        'sequence': 0,
                        'route_area': None
                    }
                )
        
        # Atualiza status da composição
        self.route_comp._sync_on_status_change('draft')
        
        # Gera relatório final
        total_plans = len(self.created_plans)
        total_deliveries = sum(p.get('deliveries', 0) for p in self.created_plans)
        total_unassigned = len([d for d in self.unassigned_global 
                               if d.id not in self.processed_deliveries])
        
        summary = (f"• {total_plans} planos criados "
                  f"• {total_deliveries} entregas processadas "
                  f"• {total_unassigned} não alocadas")

        full_url  = reverse('tmsapp:scriptapp:scripting_view', args=[self.route_comp.pk])

        self._send_progress("Roteirização concluída!", 100, status='success')
        send_notification(
         self.user_id,
         "Roteirização Concluída",
         summary, 
         level='success',
         link=full_url,
         link_name='Ver roteirização',
         action='redirect'
        )
        
        return {
            "status": "success",
            "detalhes": summary,
            "plans": self.created_plans,
            "total_deliveries": total_deliveries,
            "unassigned": total_unassigned,
            "vehicles_used": len(self.vehicle_load_plans)
        }

    def run(self):
        """Executa fluxo completo de roteirização"""
        self._update_task_record()
        
        if not self.load_deliveries():
            return {"status": "no_deliveries", "count": 0}
        
        if not self.load_areas():
            return {"status": "no_areas", "count": 0}
        
        self.assign_deliveries()
        self.build_composition()
        self.process_vehicle_config()
        
        return self.finalize()


def can_fit_delivery(vehicle, current_weight, current_volume, delivery):
    """Verifica se uma entrega cabe no veículo"""
    delivery_weight = delivery.total_weight_kg or Decimal('0')
    delivery_volume = delivery.total_volume_m3 or Decimal('0')
    
    max_weight = vehicle.max_weight_kg or Decimal('0')
    max_volume = vehicle.max_volume_m3 or Decimal('0')
    
    return (current_weight + delivery_weight <= max_weight and
            current_volume + delivery_volume <= max_volume)


@shared_task(bind=True)
def create_script_perso_task(self, user_id, tkrecord_id, vehicles_areas, start_date, end_date):
    """
    Task Celery para criação de roteirização otimizada
    """
    time_module.sleep(5)
    try:
        planner = RoutePlanner(self, user_id, tkrecord_id, vehicles_areas, start_date, end_date)
        with transaction.atomic():
            result = planner.run()
        return result
    except Exception as exc:
        send_progress(self.request.id, user_id, f"Erro: {exc}", 100, status='failure')
        send_notification(user_id, title="Erro na Roteirização", message=str(exc), level="error")
        return {"status": "error", "error": str(exc)}