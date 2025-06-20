from django.db import models
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
from django.core.cache import cache
from django.utils import timezone
from simple_history.models import HistoricalRecords
from .Route import Route
from tmsapp.deliveryApp.models import Delivery
from auditlog.registry import auditlog
from django.db.models import Max, Sum, Count, Q
from tmsapp.deliveryApp.models import Delivery, DeliveryStatus
from tmsapp.fleetApp.models import LoadPlan, LoadPlanStatus
from django.db.models.signals import pre_save
from django.dispatch import receiver


class RouteType(models.TextChoices):
    CITY    = 'city',   'Rotas por cidade'
    CUSTOM  = 'custom', 'Rota Personalizada'
    OTHER   = 'other',  'Outro'

class RouteCompositionStatus(models.TextChoices):
    DRAFT                 = 'draft',                'Rascunho'
    PLANNED               = 'planned',              'Planejada'
    AWAITING_LOADING      = 'awaiting_loading',     'Aguardando Carregamento'
    LOADING               = 'loading',              'Em Carregamento'
    IN_TRANSIT            = 'in_transit',           'Em Trânsito'
    COMPLETED             = 'completed',            'Concluída'
    CANCELLED             = 'cancelled',            'Cancelada'


class RouteComposition(models.Model):
    """
    Agrupa múltiplas rotas em uma composição, com cálculos agregados.
    """
    name = models.CharField('Nome', max_length=100, db_index=True)

    # Many-to-many com deliveries através de RouteCompositionDelivery
    deliveries = models.ManyToManyField(
        Delivery,
        through='RouteCompositionDelivery',
        related_name='route_compositions',
        verbose_name='Entregas'
    )
    
    status = models.CharField(
        'Status',
        max_length=30,
        choices=RouteCompositionStatus.choices,
        default=RouteCompositionStatus.DRAFT,
        db_index=True,
        help_text='Situação atual da roterização'
    )
    
    # Intervalo de datas usado para filtrar Deliveries na geração
    start_date = models.DateField('Data Início', null=True, blank=True, db_index=True)
    end_date   = models.DateField('Data Fim',   null=True, blank=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(
        User, verbose_name='Criado por', 
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='route_compositions_created'
    )
    load_plans_direct = models.ManyToManyField(
        LoadPlan,
        related_name='compositions_direct',
        blank=True,
        verbose_name='Planos de Carga (direto)'
    )
    
    is_active = models.BooleanField('Ativo', default=True, db_index=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Roterização'
        verbose_name_plural = 'Roterizações'
        indexes = [
            models.Index(fields=['-created_at', 'is_active']),
        ]

    def __str__(self) -> str:
        return self.name

    def get_cache_key(self, suffix=''):
        return f'route_composition_{self.pk}_{suffix}'

    def invalidate_cache(self):
        cache.delete_many([
            self.get_cache_key('stats'),
            self.get_cache_key('deliveries_count'),
        ])
    
    def _sync_on_status_change(self, new_status: str):
        # Mapeamentos de status
        print('status', new_status)
        status_map = {
            RouteCompositionStatus.DRAFT: DeliveryStatus.IN_SCRIPT,
            RouteCompositionStatus.PLANNED: DeliveryStatus.IN_LOAD,
            RouteCompositionStatus.AWAITING_LOADING: DeliveryStatus.IN_LOAD,
            RouteCompositionStatus.LOADING: DeliveryStatus.LOADED,
            RouteCompositionStatus.IN_TRANSIT: DeliveryStatus.IN_TRANSIT,
            RouteCompositionStatus.COMPLETED: DeliveryStatus.DELIVERED,
            RouteCompositionStatus.CANCELLED: DeliveryStatus.PENDING,
        }
        lp_status_map = {
            RouteCompositionStatus.DRAFT: LoadPlanStatus.DRAFT,
            RouteCompositionStatus.PLANNED: LoadPlanStatus.ROUTE_STARTED,
            RouteCompositionStatus.AWAITING_LOADING: LoadPlanStatus.AWAITING_LOADING,
            RouteCompositionStatus.LOADING: LoadPlanStatus.LOADING,
            RouteCompositionStatus.IN_TRANSIT: LoadPlanStatus.IN_TRANSIT,
            RouteCompositionStatus.COMPLETED: LoadPlanStatus.COMPLETED,
            RouteCompositionStatus.CANCELLED: LoadPlanStatus.CANCELLED,
        }
        
        delivery_target = status_map.get(new_status)
        lp_target = lp_status_map.get(new_status)
        print('delivery_target', delivery_target)
        print('lp_target', lp_target)
        
        with transaction.atomic():
            # CORREÇÃO: Para cancelamento, coletamos todas as deliveries ANTES de deletar os vínculos
            if new_status == RouteCompositionStatus.CANCELLED:
                # Coleta todas as deliveries que serão afetadas
                delivery_ids = list(
                    self.composition_deliveries.values_list('delivery_id', flat=True)
                )
                
                # Atualiza TODAS as deliveries para PENDING
                if delivery_ids:
                    Delivery.objects.filter(id__in=delivery_ids).update(
                        status=DeliveryStatus.PENDING,
                        updated_at=timezone.now()
                    )
                    print(f'Updated {len(delivery_ids)} deliveries to PENDING')
                
                # Remove os vínculos
                self.composition_deliveries.all().delete()
                
                # Atualiza load plans e remove vínculos de rotas
                to_update_lp = []
                for lp in self.load_plans_direct.all():
                    if lp.status != lp_target:
                        lp.status = lp_target
                        to_update_lp.append(lp)
                    # Remove vínculo com rota
                    if lp.route_id:
                        lp.route = None
                        to_update_lp.append(lp) if lp not in to_update_lp else None
                
                if to_update_lp:
                    print('to_update_lp', to_update_lp)
                    LoadPlan.objects.bulk_update(to_update_lp, ['status', 'route', 'updated_at'])
                    
            else:
                # Para outros status, mantém a lógica original
                # Atualiza deliveries
                to_update_d = []
                for rcd in self.composition_deliveries.select_related('delivery'):
                    d = rcd.delivery
                    if d and d.status != delivery_target:
                        d.status = delivery_target
                        to_update_d.append(d)
                if to_update_d:
                    print('to_update_d', to_update_d)
                    Delivery.objects.bulk_update(to_update_d, ['status', 'updated_at'])

                # Atualiza load plans
                to_update_lp = []
                for lp in self.load_plans_direct.all():
                    if lp.status != lp_target:
                        lp.status = lp_target
                        to_update_lp.append(lp)

                if to_update_lp:
                    print('to_update_lp', to_update_lp)
                    LoadPlan.objects.bulk_update(to_update_lp, ['status', 'updated_at'])

                # Ao planejar a rota, descartamos vínculos sem plano de carga
                if new_status == RouteCompositionStatus.PLANNED:
                    # Atualiza as deliveries antes de deletar os vínculos
                    delivery_ids = self.composition_deliveries.filter(
                        load_plan__isnull=True
                    ).values_list('delivery_id', flat=True)
                    
                    Delivery.objects.filter(id__in=delivery_ids).update(
                        status=DeliveryStatus.PENDING,
                        updated_at=timezone.now()
                    )
                    
                    # Remove os vínculos
                    self.composition_deliveries.filter(load_plan__isnull=True).delete()

            

    @property
    def total_deliveries(self) -> int:
        """
        Retorna a quantidade total de entregas associadas a esta composição.
        """
        return self.deliveries.count()

    @property
    def max_distance_km(self) -> float:
        """
        Retorna a maior distância em km entre todos os planos de carga desta composição.
        """
        result = self.composition_deliveries.aggregate(
            max_dist=Max('load_plan__route__distance_km')
        )
        return result['max_dist'] or 0.0

    @property
    def max_duration_min(self) -> float:
        """
        Retorna a maior duração em minutos entre todos os planos de carga desta composição.
        """
        result = self.composition_deliveries.aggregate(
            max_dur=Max('load_plan__route__time_min')
        )
        return result['max_dur'] or 0.0
        
    @property
    def total_load_plans(self) -> int:
        """
        Retorna o número total de planos de carga nesta composição.
        """
        return self.composition_deliveries.values('load_plan').distinct().count()

    @property
    def total_vehicles(self) -> int:
        """
        Retorna o número total de veículos utilizados nesta composição.
        """
        return self.composition_deliveries.values('load_plan__vehicle').distinct().count()
    @property
    def total_value(self) -> str:
        """Soma de todos os prices das entregas desta composição, formatado."""
        agg = self.composition_deliveries.aggregate(
            total=Sum('delivery__price')
        )
        val = float(agg['total'] or 0.0)
        s = f"{val:,.2f}"
        # troca ponto decimal por vírgula e milhar por ponto
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s

    @property
    def total_volume(self) -> str:
        """Soma de todos os volumes (m³) das entregas desta composição, formatado."""
        agg = self.composition_deliveries.aggregate(
            total=Sum('delivery__total_volume_m3')
        )
        val = float(agg['total'] or 0.0)
        s = f"{val:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s

    @property
    def total_weight(self) -> str:
        """Soma de todos os pesos (kg) das entregas desta composição, formatado."""
        agg = self.composition_deliveries.aggregate(
            total=Sum('delivery__total_weight_kg')
        )
        val = float(agg['total'] or 0.0)
        s = f"{val:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s

    @property
    def deliveries_with_loadplan(self) -> int:
        """Quantidade de entregas que já foram alocadas em um LoadPlan."""
        return self.composition_deliveries.filter(
            load_plan__isnull=False
        ).count()

    @property
    def deliveries_without_loadplan(self) -> int:
        """Quantidade de entregas que ainda não têm LoadPlan."""
        return self.composition_deliveries.filter(
            load_plan__isnull=True
        ).count()
    
    @property
    def status_label(self) -> str:
        return self.get_status_display()
    
    @property
    def load_plans(self):
        """
        Retorna todos os LoadPlan associados a esta composição:
        """
        return self.load_plans_direct.all()
        
    @property
    def unassigned_items(self):
        """
        Retorna um QuerySet contendo todos os RouteCompositionDelivery
        desta composição cujo load_plan ainda é None (ou seja, estão "fora de carga").
        """
        return self.composition_deliveries.filter(load_plan__isnull=True)   
     
    @property
    def code(self) -> str:
        return f'RTR-{self.pk}'
    
class RouteCompositionDelivery(models.Model):
    """
    Tabela intermediária entre RouteComposition e Delivery
    """
    route_composition = models.ForeignKey(
        RouteComposition,
        on_delete=models.CASCADE,
        related_name='composition_deliveries'
    )
    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name='composition_assignments'
    )
    load_plan = models.ForeignKey(
        'LoadPlan',
        verbose_name='Plano de Carga',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text='Plano de carga ao qual este pedido pertence. Null para pedidos fora de carga.',
        db_index=True
    )
    route_area = models.ForeignKey(
        'routearea',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text='Area de rota ao qual este pedido pertence. Null para pedidos fora de rota.',
        db_index=True
    )
    sequence = models.PositiveIntegerField('Sequência', default=1)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    history = HistoricalRecords()

    class Meta:
        # Garante que cada Delivery só apareça **uma única vez** em toda a tabela.
        constraints = [
            models.UniqueConstraint(
                fields=['delivery'],
                name='unique_delivery_global'
            )
        ]
        ordering = ['sequence']
        verbose_name = 'Entrega da Composição de Rota'
        verbose_name_plural = 'Entregas da Composição de Rota'
        indexes = [
            models.Index(fields=['route_composition', 'sequence']),
            models.Index(fields=['load_plan', 'delivery']),
            models.Index(fields=['delivery', 'load_plan']),
        ]
    def __str__(self) -> str:
        load_info = f"{self.load_plan.name}" if self.load_plan else "(Fora de carga)"
        return f"{self.route_composition.name} - {self.delivery}{load_info}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalida cache da composição pai
        self.route_composition.invalidate_cache()


# Signal para sincronizar status antes de salvar
@receiver(pre_save, sender=RouteComposition)
def on_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return  # novo registro
    old = sender.objects.get(pk=instance.pk)
    if old.status != instance.status:
        instance._sync_on_status_change(instance.status)
        instance.invalidate_cache()


auditlog.register(RouteComposition)
auditlog.register(RouteCompositionDelivery)
