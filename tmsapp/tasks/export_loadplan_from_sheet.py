# tmsapp/tasks/export_loadplan_from_sheet.py

from typing import Any
import pandas as pd
from django.conf import settings
from celery import shared_task
from djangonotify.utils import send_progress, send_notification
from djangonotify.models import TaskRecord

from django.db.models import QuerySet
from tmsapp.models import RouteCompositionDelivery
from django.utils import timezone
import os


class DeliveryExporter:
    """
    Exporta entregas de um RouteComposition para planilha CSV no formato do template.
    """
    def __init__(self, user_id: int, task_id: str, composition_id: int):
        self.user_id = user_id
        self.task_id = task_id
        self.composition_id = composition_id

    def build_dataframe(self, assignments: QuerySet[RouteCompositionDelivery]) -> pd.DataFrame:
        """
        Constrói um DataFrame a partir dos assignments,
        garantindo colunas e ordem do modelo de exportação.
        """
        rows: list[dict[str, Any]] = []
        for rc in assignments:
            d = rc.delivery
            lp = rc.load_plan
            # Montagem da linha conforme template
            rows.append({
                'NOME':                       'Rota 1',
                'VEICULO':                    lp.vehicle.license_plate if lp else '',
                'EVENTO':                     'serviço',
                'CODIGO LOCAL':               d.postal_code or '',
                'NOME LOCAL':                 d.customer.full_name or '',
                'ENDERECO':                   d.full_address or '',
                'PESO (kg)':                  float(d.total_weight_kg or 0),
                'VOLUME (m3)':                float(d.total_volume_m3 or 0),
                'DISTANCIA (km)':             float(lp.route.distance_km) if lp and lp.route else '',
                'TEMPO DE PERCURSO (min)':    float(lp.route.time_min) if lp and lp.route else '',
                'HORÁRIO DE CHEGADA PREVISTO': d.date_delivery or '',
                'TEMPO DE ATENDIMENTO (min)': '30 min',
                'LATITUDE':                   float(d.latitude) if d.latitude else '',
                'LONGITUDE':                  float(d.longitude) if d.longitude else '',
                'OBSERVAÇÕES':                d.observation or '',
                'INFORMAÇÃO ADICIONAL 1':     '',
                'INFORMAÇÃO ADICIONAL 2':     '',
                'NÚMERO NF':                  getattr(d, 'invoice_number', '') or '',
                'NÚMERO PEDIDO':              f"{d.filial}-{d.order_number}" if d.order_number else "",
                'OPERADOR':                   d.created_by.get_full_name() if d.created_by else '',
                'PLACA DO VEICULO':           lp.vehicle.license_plate if lp else '',
                'CÓD. TRANSPORTADORA':        getattr(d, 'transporter_code', '') or '',
                'TRANSPORTADORA':             lp.vehicle.carrier.name if lp and lp.vehicle and lp.vehicle.carrier else '',
                'NÚMERO REMESSA':             getattr(d, 'shipment_number', '') or '',
            })

        columns = [
            'NOME','VEICULO','EVENTO','CODIGO LOCAL','NOME LOCAL','ENDERECO',
            'PESO (kg)','VOLUME (m3)','DISTANCIA (km)','TEMPO DE PERCURSO (min)',
            'HORÁRIO DE CHEGADA PREVISTO','TEMPO DE ATENDIMENTO (min)','LATITUDE',
            'LONGITUDE','OBSERVAÇÕES','INFORMAÇÃO ADICIONAL 1',
            'INFORMAÇÃO ADICIONAL 2','NÚMERO NF','NÚMERO PEDIDO','OPERADOR',
            'PLACA DO VEICULO','CÓD. TRANSPORTADORA','TRANSPORTADORA','NÚMERO REMESSA'
        ]
        return pd.DataFrame(rows, columns=columns)

    def export(self) -> str:
        """
        Executa consulta, monta DataFrame e salva arquivo CSV.
        """
        # Filtra assignments desta composição com load_plan vinculado
        qs = RouteCompositionDelivery.objects.filter(
            route_composition_id=self.composition_id,
            load_plan__isnull=False
        )

        total = qs.count()
        send_progress(self.task_id, self.user_id, f"Exportando {total} entregas...", 50)

        df = self.build_dataframe(qs)
        filename = f"export_{timezone.now().strftime('%Y%m%d%H%M%S')}.csv"

        # Garante que o diretório exports existe
        export_dir = f"{settings.MEDIA_ROOT}/exports"
        os.makedirs(export_dir, exist_ok=True)

        path = f"{export_dir}/{filename}"
        
        # Exporta para CSV com encoding UTF-8 e separador de ponto-e-vírgula
        df.to_csv(path, index=False, encoding='ISO-8859-1', sep=';')

        url = f"{settings.MEDIA_URL}exports/{filename}"

        send_progress(self.task_id, self.user_id, "Exportação concluída", 100, status='success')
        send_notification(
            self.user_id,
            "Exportação de entregas concluída",
            f"Seu arquivo CSV está disponível",
            level='success',
            link=url,
            link_name='Baixar arquivo',
            action='download'
        )
        return path


@shared_task(bind=True)
def export_loadplan_from_sheet(self, user_id: int, tkrecord_id: int, composition_id: int):
    """
    Tarefa Celery para exportar entregas de uma composição de rota.
    """
    try:
        task_id = self.request.id
        tr = TaskRecord.objects.get(pk=tkrecord_id)
        tr.task_id = task_id
        tr.save(update_fields=['task_id'])

        exporter = DeliveryExporter(user_id, task_id, composition_id)
        file_path = exporter.export()
        return {"status": "success", "file_path": file_path}

    except Exception as e:
        send_progress(self.request.id, user_id, f"Erro: {e}", 100, status='failure')
        send_notification(user_id, "Falha na exportação", str(e), level='danger')
        return {"status": "error", "error": str(e)}