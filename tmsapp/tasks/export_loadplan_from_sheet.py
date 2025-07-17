# tmsapp/tasks/export_loadplan_from_sheet.py

from typing import Any, Optional, Dict, List
import pandas as pd
import os
import logging
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from celery import shared_task
from celery.exceptions import Retry

from djangonotify.utils import send_progress, send_notification
from djangonotify.models import TaskRecord
from tmsapp.models import RouteCompositionDelivery, LoadPlan, RouteComposition

import time
# Configuração do logger
logger = logging.getLogger(__name__)

# Constantes
EXPORT_CONSTANTS = {
    'ENCODING': 'ISO-8859-1',
    'SEPARATOR': ';',
    'EXPORT_DIR': 'exports',
    'DEFAULT_SERVICE_TIME': '30 min',
    'DEFAULT_ROUTE_NAME': 'Rota 1',
    'DEFAULT_EVENT_TYPE': 'serviço',
    'PROGRESS_MESSAGES': {
        'STARTING': 'Iniciando exportação...',
        'PROCESSING': 'Processando {count} entregas...',
        'BUILDING_FILE': 'Construindo arquivo CSV...',
        'SAVING_FILE': 'Salvando arquivo...',
        'COMPLETED': 'Exportação concluída com sucesso!',
        'ERROR': 'Erro durante a exportação: {error}',
    },
    'NOTIFICATION_MESSAGES': {
        'SUCCESS_TITLE': 'Exportação de entregas concluída',
        'SUCCESS_MESSAGE': 'Seu arquivo CSV está disponível para download',
        'ERROR_TITLE': 'Falha na exportação',
        'DOWNLOAD_LINK': 'Baixar arquivo',
    }
}

# Colunas da planilha de exportação
EXPORT_COLUMNS = [
    'NOME', 'VEICULO', 'EVENTO', 'CODIGO LOCAL', 'NOME LOCAL', 'ENDERECO',
    'PESO (kg)', 'VOLUME (m3)', 'DISTANCIA (km)', 'TEMPO DE PERCURSO (min)',
    'HORÁRIO DE CHEGADA PREVISTO', 'TEMPO DE ATENDIMENTO (min)', 'LATITUDE',
    'LONGITUDE', 'OBSERVAÇÕES', 'INFORMAÇÃO ADICIONAL 1',
    'INFORMAÇÃO ADICIONAL 2', 'NÚMERO NF', 'NÚMERO PEDIDO', 'OPERADOR',
    'PLACA DO VEICULO', 'CÓD. TRANSPORTADORA', 'TRANSPORTADORA', 'NÚMERO REMESSA'
]


class ExportError(Exception):
    """Exceção customizada para erros de exportação"""
    pass


class DeliveryExporter:
    """
    Classe responsável por exportar entregas de uma composição de rota
    ou de um plano de carga específico para planilha CSV.
    """
    
    def __init__(
        self,
        user_id: int,
        task_id: str,
        composition_id: Optional[int] = None,
        loadplan_id: Optional[int] = None
    ):
        """
        Inicializa o exportador de entregas.
        
        Args:
            user_id: ID do usuário que solicitou a exportação
            task_id: ID da tarefa Celery
            composition_id: ID da composição de rota (opcional)
            loadplan_id: ID do plano de carga (opcional)
        """
        self.user_id = user_id
        self.task_id = task_id
        self.composition_id = composition_id
        self.loadplan_id = loadplan_id
        self._validate_parameters()
        if self.loadplan_id is not None:
            try:
                self.loadplan = LoadPlan.objects.get(pk=self.loadplan_id)
            except LoadPlan.DoesNotExist:
                raise ObjectDoesNotExist(f"LoadPlan {self.loadplan_id} não encontrado")
        else:
            self.loadplan = None

    def _validate_parameters(self) -> None:
        """
        Valida se os parâmetros fornecidos são válidos.
        
        Raises:
            ValidationError: Se os parâmetros não forem válidos
        """
        if not self.composition_id and not self.loadplan_id:
            raise ValidationError("É necessário fornecer composition_id ou loadplan_id")
        
        if self.composition_id and self.loadplan_id:
            raise ValidationError("Forneça apenas composition_id OU loadplan_id, não ambos")

    def _get_queryset(self) -> QuerySet[RouteCompositionDelivery]:
        """
        Obtém o QuerySet apropriado baseado nos parâmetros fornecidos.
        
        Returns:
            QuerySet: QuerySet filtrado de RouteCompositionDelivery
            
        Raises:
            ObjectDoesNotExist: Se não encontrar dados para os parâmetros fornecidos
        """
        try:
            if self.loadplan_id:
                # Valida se o LoadPlan existe
                if not LoadPlan.objects.filter(id=self.loadplan_id).exists():
                    raise ObjectDoesNotExist(f"LoadPlan {self.loadplan_id} não encontrado")
                
                queryset = RouteCompositionDelivery.objects.filter(
                    load_plan_id=self.loadplan_id
                ).select_related(
                    'delivery__customer',
                    'delivery__created_by',
                    'load_plan__vehicle__carrier',
                    'load_plan__route'
                )
            else:
                # Valida se a RouteComposition existe
                if not RouteComposition.objects.filter(id=self.composition_id).exists():
                    raise ObjectDoesNotExist(f"RouteComposition {self.composition_id} não encontrada")
                
                queryset = RouteCompositionDelivery.objects.filter(
                    route_composition_id=self.composition_id,
                    load_plan__isnull=False
                ).select_related(
                    'delivery__customer',
                    'delivery__created_by',
                    'load_plan__vehicle__carrier',
                    'load_plan__route'
                )
            
            if not queryset.exists():
                raise ObjectDoesNotExist("Nenhuma entrega encontrada para os parâmetros fornecidos")
            
            return queryset
            
        except Exception as e:
            logger.error(f"Erro ao obter queryset: {str(e)}")
            raise

    def _safe_get_attr(self, obj: Any, attr: str, default: Any = '') -> Any:
        """
        Obtém um atributo de forma segura, retornando um valor padrão se não existir.
        
        Args:
            obj: Objeto do qual extrair o atributo
            attr: Nome do atributo
            default: Valor padrão se o atributo não existir
            
        Returns:
            Any: Valor do atributo ou valor padrão
        """
        try:
            return getattr(obj, attr, default) or default
        except (AttributeError, TypeError):
            return default

    def _safe_get_nested_attr(self, obj: Any, attrs: str, default: Any = '') -> Any:
        """
        Obtém um atributo aninhado de forma segura.
        
        Args:
            obj: Objeto base
            attrs: String com atributos separados por ponto (ex: 'vehicle.license_plate')
            default: Valor padrão se o atributo não existir
            
        Returns:
            Any: Valor do atributo ou valor padrão
        """
        try:
            current_obj = obj
            for attr in attrs.split('.'):
                if current_obj is None:
                    return default
                current_obj = getattr(current_obj, attr, None)
            return current_obj if current_obj is not None else default
        except (AttributeError, TypeError):
            return default

    def _format_order_number(self, delivery) -> str:
        """
        Formata o número do pedido combinando filial e número.
        
        Args:
            delivery: Objeto de entrega
            
        Returns:
            str: Número do pedido formatado
        """
        try:
            filial = self._safe_get_attr(delivery, 'filial', '')
            order_number = self._safe_get_attr(delivery, 'order_number', '')
            
            if filial and order_number:
                return f"{filial}-{order_number}"
            return order_number or ''
        except Exception:
            return ''

    def _convert_to_float(self, value: Any, default: float = 0.0) -> float:
        """
        Converte um valor para float de forma segura.
        
        Args:
            value: Valor a ser convertido
            default: Valor padrão se a conversão falhar
            
        Returns:
            float: Valor convertido ou valor padrão
        """
        try:
            if value is None or value == '':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default

    def _build_row_data(self, route_composition_delivery: RouteCompositionDelivery) -> Dict[str, Any]:
        """
        Constrói os dados de uma linha da planilha.
        
        Args:
            route_composition_delivery: Objeto RouteCompositionDelivery
            
        Returns:
            Dict: Dados da linha formatados
        """
        delivery = route_composition_delivery.delivery
        load_plan = route_composition_delivery.load_plan
        
        return {
            'NOME': EXPORT_CONSTANTS['DEFAULT_ROUTE_NAME'],
            'VEICULO': self._safe_get_nested_attr(load_plan, 'vehicle.license_plate'),
            'EVENTO': EXPORT_CONSTANTS['DEFAULT_EVENT_TYPE'],
            'CODIGO LOCAL': self._safe_get_attr(delivery, 'postal_code'),
            'NOME LOCAL': self._safe_get_nested_attr(delivery, 'customer.full_name'),
            'ENDERECO': self._safe_get_attr(delivery, 'full_address'),
            'PESO (kg)': self._convert_to_float(self._safe_get_attr(delivery, 'total_weight_kg')),
            'VOLUME (m3)': self._convert_to_float(self._safe_get_attr(delivery, 'total_volume_m3')),
            'DISTANCIA (km)': self._convert_to_float(self._safe_get_nested_attr(load_plan, 'route.distance_km')),
            'TEMPO DE PERCURSO (min)': self._convert_to_float(self._safe_get_nested_attr(load_plan, 'route.time_min')),
            'HORÁRIO DE CHEGADA PREVISTO': self._safe_get_attr(delivery, 'date_delivery'),
            'TEMPO DE ATENDIMENTO (min)': EXPORT_CONSTANTS['DEFAULT_SERVICE_TIME'],
            'LATITUDE': self._convert_to_float(self._safe_get_attr(delivery, 'latitude')),
            'LONGITUDE': self._convert_to_float(self._safe_get_attr(delivery, 'longitude')),
            'OBSERVAÇÕES': self._safe_get_attr(delivery, 'observation'),
            'INFORMAÇÃO ADICIONAL 1': '',
            'INFORMAÇÃO ADICIONAL 2': '',
            'NÚMERO NF': self._safe_get_attr(delivery, 'invoice_number'),
            'NÚMERO PEDIDO': self._format_order_number(delivery),
            'OPERADOR': self._safe_get_nested_attr(delivery, 'created_by.get_full_name', ''),
            'PLACA DO VEICULO': self._safe_get_nested_attr(load_plan, 'vehicle.license_plate'),
            'CÓD. TRANSPORTADORA': self._safe_get_attr(delivery, 'transporter_code'),
            'TRANSPORTADORA': self._safe_get_nested_attr(load_plan, 'vehicle.carrier.name'),
            'NÚMERO REMESSA': self._safe_get_attr(delivery, 'shipment_number'),
        }

    def _build_dataframe(self, assignments: QuerySet[RouteCompositionDelivery]) -> pd.DataFrame:
        """
        Constrói um DataFrame pandas a partir dos assignments.
        
        Args:
            assignments: QuerySet de RouteCompositionDelivery
            
        Returns:
            pd.DataFrame: DataFrame formatado para exportação
        """
        try:
            rows: List[Dict[str, Any]] = []
            
            for assignment in assignments:
                row_data = self._build_row_data(assignment)
                rows.append(row_data)
            
            return pd.DataFrame(rows, columns=EXPORT_COLUMNS)
            
        except Exception as e:
            logger.error(f"Erro ao construir DataFrame: {str(e)}")
            raise ExportError(f"Erro ao processar dados: {str(e)}")

    def _generate_filename(self) -> str:
        """
        Gera um nome único para o arquivo de exportação.
        
        Returns:
            str: Nome do arquivo
        """
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        if self.composition_id is not None:
            export_type = "Roteiro"
        else:
            export_type = self.loadplan.name or "Carga"
        return f"{export_type}_{timestamp}.csv"

    def _ensure_export_directory(self) -> str:
        """
        Garante que o diretório de exportação existe.
        
        Returns:
            str: Caminho do diretório de exportação
        """
        try:
            export_dir = os.path.join(settings.MEDIA_ROOT, EXPORT_CONSTANTS['EXPORT_DIR'])
            os.makedirs(export_dir, exist_ok=True)
            return export_dir
        except Exception as e:
            logger.error(f"Erro ao criar diretório de exportação: {str(e)}")
            raise ExportError(f"Erro ao criar diretório: {str(e)}")

    def _save_dataframe(self, dataframe: pd.DataFrame, file_path: str) -> None:
        """
        Salva o DataFrame em um arquivo CSV.
        
        Args:
            dataframe: DataFrame a ser salvo
            file_path: Caminho completo do arquivo
        """
        try:
            dataframe.to_csv(
                file_path,
                index=False,
                encoding=EXPORT_CONSTANTS['ENCODING'],
                sep=EXPORT_CONSTANTS['SEPARATOR']
            )
            logger.info(f"Arquivo salvo com sucesso: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo: {str(e)}")
            raise ExportError(f"Erro ao salvar arquivo: {str(e)}")

    def _send_progress_update(self, message: str, progress: int, status: str = 'info') -> None:
        """
        Envia uma atualização de progresso para o usuário.
        
        Args:
            message: Mensagem de progresso
            progress: Porcentagem de progresso (0-100)
            status: Status da operação ('info', 'success', 'error')
        """
        try:
            send_progress(self.task_id, self.user_id, message, progress, status=status)
        except Exception as e:
            logger.warning(f"Erro ao enviar progresso: {str(e)}")

    def _send_completion_notification(self, file_url: str) -> None:
        """
        Envia notificação de conclusão da exportação.
        
        Args:
            file_url: URL do arquivo exportado
        """
        try:
            send_notification(
                self.user_id,
                EXPORT_CONSTANTS['NOTIFICATION_MESSAGES']['SUCCESS_TITLE'],
                EXPORT_CONSTANTS['NOTIFICATION_MESSAGES']['SUCCESS_MESSAGE'],
                level='success',
                link=file_url,
                link_name=EXPORT_CONSTANTS['NOTIFICATION_MESSAGES']['DOWNLOAD_LINK'],
                action='download'
            )
        except Exception as e:
            logger.warning(f"Erro ao enviar notificação: {str(e)}")

    def _send_error_notification(self, error_message: str) -> None:
        """
        Envia notificação de erro na exportação.
        
        Args:
            error_message: Mensagem de erro
        """
        try:
            send_notification(
                self.user_id,
                EXPORT_CONSTANTS['NOTIFICATION_MESSAGES']['ERROR_TITLE'],
                error_message,
                level='danger'
            )
        except Exception as e:
            logger.warning(f"Erro ao enviar notificação de erro: {str(e)}")

    def export(self) -> str:
        """
        Executa o processo completo de exportação.
        
        Returns:
            str: Caminho do arquivo exportado
            
        Raises:
            ExportError: Se houver erro durante a exportação
        """
        try:
            # Inicia o processo
            self._send_progress_update(
                EXPORT_CONSTANTS['PROGRESS_MESSAGES']['STARTING'], 
                10
            )
            
            # Obtém os dados
            queryset = self._get_queryset()
            total_records = queryset.count()
            
            self._send_progress_update(
                EXPORT_CONSTANTS['PROGRESS_MESSAGES']['PROCESSING'].format(count=total_records),
                30
            )
            
            # Constrói o DataFrame
            self._send_progress_update(
                EXPORT_CONSTANTS['PROGRESS_MESSAGES']['BUILDING_FILE'],
                50
            )
            
            dataframe = self._build_dataframe(queryset)
            
            # Prepara o arquivo
            self._send_progress_update(
                EXPORT_CONSTANTS['PROGRESS_MESSAGES']['SAVING_FILE'],
                70
            )
            

            export_dir = self._ensure_export_directory()
            filename = self._generate_filename()
            file_path = os.path.join(export_dir, filename)
            
            # Salva o arquivo
            self._save_dataframe(dataframe, file_path)
            
            # Gera URL do arquivo
            file_url = f"{settings.MEDIA_URL}{EXPORT_CONSTANTS['EXPORT_DIR']}/{filename}"
            
            # Finaliza com sucesso
            self._send_progress_update(
                EXPORT_CONSTANTS['PROGRESS_MESSAGES']['COMPLETED'],
                100,
                'success'
            )
            
            self._send_completion_notification(file_url)
            
            logger.info(f"Exportação concluída com sucesso. Arquivo: {file_path}")
            return file_path
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Erro durante exportação: {error_message}")
            
            self._send_progress_update(
                EXPORT_CONSTANTS['PROGRESS_MESSAGES']['ERROR'].format(error=error_message),
                100,
                'failure'
            )
            
            self._send_error_notification(error_message)
            raise ExportError(error_message)


def _update_task_record(task_record_id: int, celery_task_id: str) -> None:
    """
    Atualiza o registro da tarefa com o ID do Celery.
    
    Args:
        task_record_id: ID do registro da tarefa
        celery_task_id: ID da tarefa no Celery
    """
    try:
        with transaction.atomic():
            task_record = TaskRecord.objects.get(pk=task_record_id)
            task_record.task_id = celery_task_id
            task_record.save(update_fields=['task_id'])
    except TaskRecord.DoesNotExist:
        logger.error(f"TaskRecord {task_record_id} não encontrado")
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar TaskRecord {task_record_id}: {str(e)}")
        raise


def _handle_task_error(task_id: str, user_id: int, error: Exception) -> Dict[str, Any]:
    """
    Trata erros que ocorrem durante a execução da tarefa.
    
    Args:
        task_id: ID da tarefa
        user_id: ID do usuário
        error: Exceção que ocorreu
        
    Returns:
        Dict: Resultado com informações do erro
    """
    error_message = str(error)
    logger.error(f"Erro na tarefa {task_id}: {error_message}")
    
    try:
        send_progress(task_id, user_id, f"Erro: {error_message}", 100, status='failure')
        send_notification(
            user_id,
            EXPORT_CONSTANTS['NOTIFICATION_MESSAGES']['ERROR_TITLE'],
            error_message,
            level='danger'
        )
    except Exception as notification_error:
        logger.error(f"Erro ao enviar notificação: {str(notification_error)}")
    
    return {"status": "error", "error": error_message}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def export_loadplan_from_sheet(self, user_id: int, tkrecord_id: int, composition_id: int) -> Dict[str, Any]:
    """
    Tarefa Celery para exportar entregas de uma composição de rota.
    
    Args:
        user_id: ID do usuário que solicitou a exportação
        tkrecord_id: ID do registro da tarefa
        composition_id: ID da composição de rota
        
    Returns:
        Dict: Resultado da operação
    """
    task_id = self.request.id
    
    try:
        time.sleep(5)
        # Atualiza o registro da tarefa
        _update_task_record(tkrecord_id, task_id)
        
        # Executa a exportação
        exporter = DeliveryExporter(
            user_id=user_id,
            task_id=task_id,
            composition_id=composition_id
        )
        
        file_path = exporter.export()
        
        logger.info(f"Exportação por composição concluída. Usuário: {user_id}, Composição: {composition_id}")
        return {"status": "success", "file_path": file_path}
        
    except (ValidationError, ObjectDoesNotExist, ExportError) as e:
        # Erros conhecidos, não faz retry
        return _handle_task_error(task_id, user_id, e)
        
    except Exception as e:
        # Outros erros podem ser retentados
        logger.warning(f"Erro inesperado na exportação, tentativa {self.request.retries + 1}: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        else:
            return _handle_task_error(task_id, user_id, e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def export_loadplan_by_loadplan(self, user_id: int, tkrecord_id: int, loadplan_id: int) -> Dict[str, Any]:
    """
    Tarefa Celery para exportar entregas de um plano de carga específico.
    
    Args:
        user_id: ID do usuário que solicitou a exportação
        tkrecord_id: ID do registro da tarefa
        loadplan_id: ID do plano de carga
        
    Returns:
        Dict: Resultado da operação
    """
    task_id = self.request.id
    try:
        time.sleep(5)
        # Atualiza o registro da tarefa
        _update_task_record(tkrecord_id, task_id)
        
        # Executa a exportação
        exporter = DeliveryExporter(
            user_id=user_id,
            task_id=task_id,
            loadplan_id=loadplan_id
        )
        
        file_path = exporter.export()
        
        logger.info(f"Exportação por loadplan concluída. Usuário: {user_id}, LoadPlan: {loadplan_id}")
        return {"status": "success", "file_path": file_path}
        
    except (ValidationError, ObjectDoesNotExist, ExportError) as e:
        # Erros conhecidos, não faz retry
        return _handle_task_error(task_id, user_id, e)
        
    except Exception as e:
        # Outros erros podem ser retentados
        logger.warning(f"Erro inesperado na exportação, tentativa {self.request.retries + 1}: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        else:
            return _handle_task_error(task_id, user_id, e)