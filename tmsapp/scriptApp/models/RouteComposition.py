from django.db import models
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
from django.core.cache import cache
from simple_history.models import HistoricalRecords
from .Route import Route
from tmsapp.deliveryApp.models import Delivery
from auditlog.registry import auditlog
from tmsapp.fleetApp.models import LoadPlan
from django.db.models import Max, Sum, Count, Q

class RouteType(models.TextChoices):
    CITY    = 'city',   'Rotas por cidade'
    UNIQUE  = 'unique', 'Rota única'
    CUSTOM  = 'custom', 'Rota Personalizada'
    OTHER   = 'other',  'Outro'

class RouteCompositionStatus(models.TextChoices):
    DRAFT      = 'draft',     'rascunho'
    COMPLETED   = 'completed',   'completa'
    CANCELLED   = 'cancelled',  'cancelada'


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
        max_length=15,
        choices=RouteCompositionStatus.choices,
        default=RouteCompositionStatus.DRAFT,
        db_index=True,
        help_text='Situação atual da roterização'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, verbose_name='Criado por', 
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='route_compositions_created'
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
        """Gera chave de cache para este objeto"""
        return f'route_composition_{self.pk}_{suffix}'

    def invalidate_cache(self):
        """Invalida cache relacionado a esta composição"""
        cache.delete_many([
            self.get_cache_key('stats'),
            self.get_cache_key('deliveries_count'),
        ])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invalidate_cache()

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
        Retorna um queryset com todos os LoadPlan distintos
        associados a esta composição de rota.
        """
        return LoadPlan.objects.filter(
            pk__in=self.composition_deliveries
                       .values_list('load_plan_id', flat=True)
                       .distinct()
        )
    
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
    sequence = models.PositiveIntegerField('Sequência', default=1)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    def __str__(self) -> str:
        load_info = f"{self.load_plan.name}" if self.load_plan else "(Fora de carga)"
        return f"{self.route_composition.name} - {self.delivery}{load_info}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalida cache da composição pai
        self.route_composition.invalidate_cache()


auditlog.register(RouteComposition)
auditlog.register(RouteCompositionDelivery)
