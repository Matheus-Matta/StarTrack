# tmsapp/scriptApp/views.py
import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from django.contrib import messages
from django.template.loader import render_to_string
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from tmsapp.scriptApp.models import RouteCompositionDelivery, RouteComposition
from tmsapp.fleetApp.models import LoadPlan, LoadPlanStatus
from tmsapp.deliveryApp.models import Delivery, DeliveryStatus
from tmsapp.scriptApp.action.update_deliverys_route import update_deliverys_route, send_route_update_via_ws
from tmsapp.action import calc_routes


@dataclass
class ServiceResponse:
    """Padroniza respostas dos serviços"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    status_code: int = 200


class LoadPlanRepository:
    """Repository para operações de LoadPlan"""
    
    @staticmethod
    def get_with_relations(plan_id: int) -> LoadPlan:
        """Busca LoadPlan com todas as relações necessárias"""
        return LoadPlan.objects.select_related(
            'route__route_area',
            'vehicle__driver',
            'vehicle__carrier'
        ).get(pk=plan_id)
    
    @staticmethod
    def get_route_deliveries(plan: LoadPlan):
        """Obtém entregas da rota ordenadas por posição"""
        if not plan.route:
            return []
        
        return (
            plan.route.routedelivery_set
            .select_related('delivery__customer')
            .order_by('position')
        )


class DataSerializer:
    """Serializador de dados para diferentes entidades"""
    
    @staticmethod
    def serialize_plan(plan: LoadPlan, scripting: Optional[RouteComposition] = None) -> Dict[str, Any]:
        """Serializa dados do plano de carga"""
        return {
            'id': plan.id,
            'name': getattr(plan, 'name', ''),
            'is_volume_overloaded': plan.is_volume_overloaded,
            'is_weight_overloaded': plan.is_weight_overloaded,
            'code': getattr(plan, 'code', ''),
            'status': getattr(plan, 'status', ''),
            'route': DataSerializer._serialize_route(plan.route),
            'planned_date': plan.planned_date.isoformat() if plan.planned_date else '',
            'vehicle': DataSerializer._serialize_vehicle(plan.vehicle),
            'totals': DataSerializer._serialize_totals(plan)
        }
    
    @staticmethod
    def _serialize_route(route) -> Dict[str, Any]:
        """Serializa dados da rota"""
        if not route:
            return {'id': 0, 'route_area': {'id': 0, 'name': '', 'hex_color': ''}}
        
        route_area = route.route_area if route.route_area else None
        return {
            'id': route.id,
            'route_area': {
                'id': route_area.id if route_area else 0,
                'name': route_area.name if route_area else '',
                'hex_color': route_area.hex_color if route_area else ''
            }
        }
    
    @staticmethod
    def _serialize_vehicle(vehicle) -> Optional[Dict[str, Any]]:
        """Serializa dados do veículo"""
        if not vehicle:
            return None
        
        vehicle_data = {
            'id': vehicle.id,
            'license_plate': getattr(vehicle, 'license_plate', ''),
            'type': DataSerializer._get_vehicle_type(vehicle),
            'max_weight_kg': getattr(vehicle, 'formatted_max_weight_kg', ''),
            'max_volume_m3': getattr(vehicle, 'formatted_max_volume_m3', ''),
            'driver': DataSerializer._serialize_driver(vehicle.driver)
        }
        
        # Adiciona carrier se existir
        if hasattr(vehicle, 'carrier') and vehicle.carrier:
            vehicle_data['carrier'] = {
                'id': vehicle.carrier.id,
                'name': getattr(vehicle.carrier, 'name', ''),
                'phone': getattr(vehicle.carrier, 'phone', '')
            }
        
        return vehicle_data
    
    @staticmethod
    def _get_vehicle_type(vehicle) -> str:
        """Obtém tipo do veículo de forma segura"""
        if hasattr(vehicle, 'get_vehicle_type') and callable(vehicle.get_vehicle_type):
            return vehicle.get_vehicle_type()
        return getattr(vehicle, 'type', '')
    
    @staticmethod
    def _serialize_driver(driver) -> Optional[Dict[str, Any]]:
        """Serializa dados do motorista"""
        if not driver:
            return None
        
        return {
            'id': driver.id,
            'name': f"{getattr(driver, 'first_name', '')} {getattr(driver, 'last_name', '')}".strip(),
            'phone': getattr(driver, 'phone', ''),
            'is_outsourced': getattr(driver, 'is_outsourced', False)
        }
    
    @staticmethod
    def _serialize_totals(plan) -> Dict[str, Any]:
        """Serializa dados dos totais"""
        return {
            'deliveries': getattr(plan, 'total_deliveries', 0),
            'area_deliveries': getattr(plan, 'total_area_deliveries', 0),
            'weight_kg': getattr(plan, 'formatted_total_weight_kg', '0'),
            'max_weight_kg': getattr(plan, 'formatted_max_weight_kg', '0'),
            'volume_m3': getattr(plan, 'formatted_total_volume_m3', '0'),
            'max_volume_m3': getattr(plan, 'formatted_max_volume_m3', '0'),
            'value': getattr(plan, 'formatted_total_value', '0'),
            'overloaded': plan.is_overloaded() if hasattr(plan, 'is_overloaded') else False
        }
    
    @staticmethod
    def serialize_delivery(delivery, order_field: int, order_field_name: str) -> Dict[str, Any]:
        """Serializa dados de entrega"""
        if not delivery:
            return {}
        
        return {
            order_field_name: order_field,
            'id': delivery.id,
            'order_number': getattr(delivery, 'order_number', ''),
            'code': getattr(delivery, 'code', ''),
            'client': getattr(delivery.customer, 'full_name', '') if delivery.customer else '',
            'address': getattr(delivery, 'full_address_and_postal_code', ''),
            'status': getattr(delivery, 'status', ''),
            'weight_kg': getattr(delivery, 'total_weight_kg', 0),
            'volume_m3': getattr(delivery, 'total_volume_m3', 0),
            'filial': getattr(delivery, 'filial', ''),
            'observation': getattr(delivery, 'observation', ''),
            'price': getattr(delivery, 'price', 0)
        }


class LoadPlanService:
    """Serviço principal para lógica de negócio do LoadPlan"""
    
    def __init__(self):
        self.repository = LoadPlanRepository()
        self.serializer = DataSerializer()
    
    def get_plan_details(self, plan_id: int, scripting: RouteComposition) -> ServiceResponse:
        """Obtém detalhes completos do plano de carga"""
        try:
            self._validate_plan_id(plan_id)
            
            plan = self.repository.get_with_relations(plan_id)
            plan_data = self.serializer.serialize_plan(plan, scripting)
            stops = self._get_route_stops(plan)
            extras = self._get_extra_deliveries(plan, scripting)
            
            print(f"LoadPlan {plan_id} - Stops: {len(stops)}, Extras: {len(extras)}")
            
            return ServiceResponse(
                success=True,
                data={
                    'plan': plan_data,
                    'stops': stops,
                    'extras': extras
                }
            )
            
        except ValidationError as e:
            return ServiceResponse(
                success=False,
                error_message=str(e),
                status_code=400
            )
        except ObjectDoesNotExist:
            return ServiceResponse(
                success=False,
                error_message=f'Plano de carga #{plan_id} não encontrado',
                status_code=404
            )
        except Exception as e:
            print(f"Erro inesperado ao carregar LoadPlan {plan_id}: {str(e)}", exc_info=True)
            return ServiceResponse(
                success=False,
                error_message='Erro interno do servidor',
                status_code=500
            )
    
    def update_plan_deliveries(self, delivery_ids: List[int], loadplan_id: int, 
                               scripting_id: int, method: str) -> ServiceResponse:
        """Atualiza entregas do plano de carga"""
        try:
            # Validações iniciais
            self._validate_update_params(delivery_ids, loadplan_id, scripting_id, method)
            composition = RouteComposition.objects.get(pk=scripting_id)
            # fluxo normal, loadplan != 0
            loadplan = LoadPlan.objects.get(pk=loadplan_id)
            # Atualiza associação (POST ou DELETE)
            update_deliverys_route(delivery_ids, loadplan, composition, method)
            # Recalcula rota
            calc_routes(loadplan.route, composition, loadplan_id)
            # Notifica via WebSocket (apenas esse loadplan)
            send_route_update_via_ws(composition, loadplan_id)
            # Prepara resposta...
            updated_plan = self.repository.get_with_relations(loadplan_id)
            plan_data = self.serializer.serialize_plan(updated_plan)

            return ServiceResponse(
                success=True,
                data={
                    'method': method,
                    'plan': plan_data,
                    'scripting': {
                        'id': composition.id,
                        'total_deliveries': composition.deliveries_with_loadplan,
                        'total_deliveries_unassigned': composition.deliveries_without_loadplan
                    }
                }
            )

        except Exception as e:
            print(f"Erro inesperado ao atualizar LoadPlan {loadplan_id}: {str(e)}")
            return ServiceResponse(
                success=False,
                error_message='Erro interno do servidor',
                status_code=500
            )
    
    def _validate_plan_id(self, plan_id: int) -> None:
        """Valida ID do plano"""
        if not plan_id or not str(plan_id).isdigit():
            raise ValidationError('ID do plano inválido')
    
    def _validate_update_params(self, delivery_ids: List[int], loadplan_id: int, 
                               scripting_id: int, method: str) -> None:
        """Valida parâmetros de atualização"""
        if not delivery_ids or not loadplan_id:
            raise ValidationError('delivery_ids e loadplan_id são obrigatórios')
        
        if method.upper() not in ['POST', 'DELETE']:
            raise ValidationError('Método deve ser POST ou DELETE')
    
    def _get_route_stops(self, plan: LoadPlan) -> List[Dict[str, Any]]:
        """Obtém paradas da rota"""
        if not plan.route:
            print(f"LoadPlan {plan.id} não possui rota associada")
            return []
        
        route_deliveries = self.repository.get_route_deliveries(plan)
        stops = []
        
        for rd in route_deliveries:
            try:
                stop_data = self.serializer.serialize_delivery(
                    rd.delivery, rd.position, 'position'
                )
                stops.append(stop_data)
            except Exception as e:
                print(f"Erro ao serializar stop {rd.id}: {str(e)}")
                continue
        
        return stops
    
    def _get_extra_deliveries(self, plan: LoadPlan, scripting: RouteComposition) -> List[Dict[str, Any]]:
        """Obtém entregas extras (sem load_plan na mesma composição)"""
        if not scripting:
            print(f"LoadPlan {plan.id} não possui scripting associado")
            return []
        
        extras_qs = scripting.unassigned_items
        extras = []
        
        for rcd in extras_qs:
            try:
                extra_data = self.serializer.serialize_delivery(
                    rcd.delivery, rcd.sequence, 'sequence'
                )
                extras.append(extra_data)
            except Exception as e:
                print(f"Erro ao serializar extra delivery {rcd.id}: {str(e)}")
                continue
        
        return extras


class ResponseHelper:
    """Helper para padronizar respostas HTTP"""
    
    @staticmethod
    def json_response(service_response: ServiceResponse, **kwargs) -> JsonResponse:
        """Converte ServiceResponse em JsonResponse"""
        if service_response.success:
            return JsonResponse({
                'success': True,
                **service_response.data
            }, status=service_response.status_code)
        else:
            return JsonResponse({
                'error': True,
                'message': service_response.error_message
            }, status=service_response.status_code)
    
    @staticmethod
    def template_response(service_response: ServiceResponse, template_path: str, 
                         request: HttpRequest, **template_context) -> JsonResponse:
        """Renderiza template e retorna JsonResponse"""
        if not service_response.success:
            return ResponseHelper.json_response(service_response)
        
        html = render_to_string(
            template_path,
            {**service_response.data, **template_context},
            request=request
        )
        
        return JsonResponse({
            'success': True,
            'html': html
        })


# VIEWS
@login_required
def loadplan_details(request: HttpRequest, scripting_id: int, plan_id: int) -> JsonResponse:
    """View para exibir detalhes do plano de carga"""
    scripting = get_object_or_404(RouteComposition, pk=scripting_id)
    service = LoadPlanService()
    
    result = service.get_plan_details(plan_id, scripting)
    
    return ResponseHelper.template_response(
        result,
        'pages/routes/loadplan_details.html',
        request,
        scripting=scripting
    )


@login_required
def update_loadplan_delivery(request: HttpRequest) -> JsonResponse:
    """View para atualizar entregas do plano de carga"""
    try:
        payload = json.loads(request.body)
        delivery_ids = payload.get('delivery_ids', [])
        loadplan_id = payload.get('loadplan_id')
        scripting_id = payload.get('scripting_id')
        method = payload.get('method', 'POST').upper()
        
        service = LoadPlanService()
        result = service.update_plan_deliveries(
            delivery_ids, loadplan_id, scripting_id, method
        )
        
        return ResponseHelper.json_response(result)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': True,
            'message': 'JSON inválido na requisição'
        }, status=400)
    except Exception as e:
        print(f"Erro inesperado na view update_loadplan_delivery: {str(e)}")
        return JsonResponse({
            'error': True,
            'message': 'Erro interno do servidor'
        }, status=500)

@login_required
def delete_loadplan(request: HttpRequest, scripting_id: int, plan_id: int) -> HttpResponse:
    """View para deletar um plano de carga"""
    try:
        loadplan = get_object_or_404(LoadPlan, pk=plan_id)
        comp = get_object_or_404(RouteComposition, pk=scripting_id)
        loadplan.delete()
        messages.success(request, f'Plano de carga {loadplan.name} deletado com sucesso')
        return redirect('tmsapp:scriptapp:scripting_view', comp.id)

    except ObjectDoesNotExist:
        messages.error(request, f'plano de carga {plan_id} nao encontrado')
        return redirect('tmsapp:scriptapp:scripting_view', scripting_id)
    except Exception as e:
        messages.error(request, f'Erro ao deletar plano de carga {str(e)}')
        return redirect('tmsapp:scriptapp:scripting_view', scripting_id)

