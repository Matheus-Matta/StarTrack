from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.cache import cache
from django.db import transaction

from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog

from .vehicle import Vehicle
from tmsapp.scriptApp.models import Route


class LoadPlan(models.Model):
    """Plano de carregamento: define veículo e rota, sem ligação direta com deliveries."""
    STATUS_CHOICES = [
        ('draft',     'Rascunho'),
        ('planned',   'Planejado'),
        ('loading',   'Carregando'),
        ('departed',  'Saiu para Entrega'),
        ('completed', 'Concluído'),
        ('cancelled', 'Cancelado'),
    ]

    name = models.CharField('Nome do Plano', max_length=100, db_index=True)
    route = models.ForeignKey(
        Route,
        on_delete=models.PROTECT,
        verbose_name='Rota',
        db_index=True
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        verbose_name='Veículo',
        db_index=True
    )
    planned_date = models.DateField('Data Planejada', auto_now_add=True, db_index=True)
    departure_time = models.TimeField('Horário de Saída', null=True, blank=True)
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )

    # Capacidades herdadas do veículo
    max_weight_kg = models.DecimalField(
        'Capacidade Peso (kg)',
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))]
    )
    max_volume_m3 = models.DecimalField(
        'Capacidade Volume (m³)',
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))]
    )

    # Totais calculados (atualizados via RouteCompositionDelivery)
    total_deliveries = models.PositiveIntegerField('Total de Entregas', default=0, editable=False)

    total_weight_kg = models.FloatField(
        'Peso Total (kg)',
        default=0.0,
        editable=False
    )
    total_volume_m3 = models.FloatField(
        'Volume Total (m³)',
        default=0.0,
        editable=False
    )

    weight_utilization_pct = models.FloatField(
        'Utilização Peso (%)',
        default=0.0,
        editable=False
    )

    volume_utilization_pct = models.FloatField(
        'Utilização Volume (%)',
        default=0.0,
        editable=False
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='load_plans_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Plano de Carga'
        verbose_name_plural = 'Planos de Carga'
        ordering = ['-planned_date', '-created_at']
        indexes = [
            models.Index(fields=['-planned_date', 'status']),
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['route', 'planned_date']),
        ]

    def __str__(self):
        return f"{self.name} - {self.vehicle.name} ({self.planned_date})"

    def save(self, *args, **kwargs):
        # Ao criar, herda capacidades do veículo
        if not self.pk and self.vehicle:
            self.max_weight_kg = self.vehicle.max_weight_kg
            self.max_volume_m3 = self.vehicle.max_volume_m3
        
        super().save(*args, **kwargs)
        
        # Recalcula totais após salvar
        self.calculate_totals()

    def get_cache_key(self, suffix=''):
        return f'load_plan_{self.pk}_{suffix}'

    @property
    def code(self):
        return f'PLC-{self.pk}'

    def invalidate_cache(self):
        cache.delete_many([
            self.get_cache_key('totals'),
            self.get_cache_key('utilization'),
        ])

    @transaction.atomic
    def calculate_totals(self):
        from tmsapp.scriptApp.models.RouteComposition import RouteCompositionDelivery
        composition_deliveries = RouteCompositionDelivery.objects.filter(
            load_plan=self
        ).select_related('delivery')

        self.total_deliveries = composition_deliveries.count()
        if self.total_deliveries > 0:
            total_w = sum(cd.delivery.total_weight_kg or Decimal('0.000') for cd in composition_deliveries)
            total_v = sum(cd.delivery.total_volume_m3 or Decimal('0.000') for cd in composition_deliveries)
            self.total_weight_kg = total_w
            self.total_volume_m3 = total_v
            if self.max_weight_kg > 0:
                self.weight_utilization_pct = (total_w / self.max_weight_kg * 100).quantize(Decimal('0.01'))
            if self.max_volume_m3 > 0:
                self.volume_utilization_pct = (total_v / self.max_volume_m3 * 100).quantize(Decimal('0.01'))
        else:
            self.total_weight_kg = Decimal('0.000')
            self.total_volume_m3 = Decimal('0.000')
            self.weight_utilization_pct = Decimal('0.00')
            self.volume_utilization_pct = Decimal('0.00')

        LoadPlan.objects.filter(pk=self.pk).update(
            total_deliveries=self.total_deliveries,
            total_weight_kg=self.total_weight_kg,
            total_volume_m3=self.total_volume_m3,
            weight_utilization_pct=self.weight_utilization_pct,
            volume_utilization_pct=self.volume_utilization_pct
        )
        self.invalidate_cache()

    def is_overloaded(self) -> bool:
        return (
            self.total_weight_kg > self.max_weight_kg or
            self.total_volume_m3 > self.max_volume_m3
        )

    def remaining_capacity(self) -> dict:
        return {
            'weight_kg': max(Decimal('0.000'), self.max_weight_kg - self.total_weight_kg),
            'volume_m3': max(Decimal('0.000'), self.max_volume_m3 - self.total_volume_m3),
        }
    
    @property
    def total_value(self) -> Decimal:
        """
        Retorna o valor total (soma de `price`) de todas as entregas
        deste load plan.
        """
        from tmsapp.scriptApp.models.RouteComposition import RouteCompositionDelivery

        cds = RouteCompositionDelivery.objects.filter(load_plan=self).select_related('delivery')
        total = sum((cd.delivery.price or Decimal('0.00')) for cd in cds)
        return total.quantize(Decimal('0.01'))
    
    @property
    def formatted_total_weight_kg(self) -> str:
        w = self.total_weight_kg or 0.0
        s = f"{w:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s}"

    @property
    def formatted_total_volume_m3(self) -> str:
        v = self.total_volume_m3 or 0.0
        s = f"{v:,.2f}"
        s = s.replace(",", "X").replace("X", ".")
        return f"{s}"

    @property
    def formatted_total_value(self) -> str:
        val = float(self.total_value or 0)
        s = f"{val:,.2f}"
        s = s.replace(",", "X").replace("X", ".")
        return f"{s}"
    
    @property
    def formatted_max_weight_kg(self) -> str:
        w = float(self.max_weight_kg or 0)
        s = f"{w:,.2f}"
        s = s.replace(",", "X").replace("X", ".")
        return f"{s}"

    @property
    def formatted_max_volume_m3(self) -> str:
        v = float(self.max_volume_m3 or 0)
        s = f"{v:,.2f}"
        s = s.replace(",", "X").replace("X", ".")
        return f"{s}"

    @property
    def total_area_deliveries(self) -> int:
        """
        Retorna o total de entregas distintas (por delivery_id)
        para todos os LoadPlans da mesma área.
        """
        from tmsapp.scriptApp.models.RouteComposition import RouteCompositionDelivery

        area = self.route.route_area
        return RouteCompositionDelivery.objects.filter(
            load_plan__route__route_area=area
        ).values('delivery').distinct().count()
auditlog.register(LoadPlan)
