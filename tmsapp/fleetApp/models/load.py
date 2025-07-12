from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from auditlog.registry import auditlog
from .vehicle import Vehicle
from tmsapp.scriptApp.models import Route
from simple_history.models import HistoricalRecords

class LoadPlanStatus(models.TextChoices):
    DRAFT                 = 'draft',                'Rascunho'
    ROUTE_STARTED         = 'route_started',        'Roteiro Iniciado'
    AWAITING_LOADING      = 'awaiting_loading',     'Aguardando Carregamento'
    LOADING               = 'loading',              'Em Carregamento'
    LOADED                = 'loaded',               'Carregado'
    IN_TRANSIT            = 'in_transit',           'Em Trânsito'
    COMPLETED             = 'completed',            'Concluído'
    CANCELLED             = 'cancelled',            'Cancelado'
    
class LoadPlan(models.Model):
    """Plano de carregamento: define veículo e rota, sem ligação direta com deliveries."""

    name = models.CharField('Nome do Plano', max_length=100, db_index=True)
    route = models.ForeignKey(Route, on_delete=models.PROTECT, verbose_name='Rota', db_index=True, null=True, blank=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, verbose_name='Veículo', db_index=True)
    planned_date = models.DateField('Data Planejada', auto_now_add=True, db_index=True)
    departure_time = models.TimeField('Horário de Saída', null=True, blank=True)
    status = models.CharField('Status',
                            max_length=50,
                            choices=LoadPlanStatus.choices,
                            default=LoadPlanStatus.DRAFT,
                            db_index=True)

    # Capacidades herdadas do veículo
    max_weight_kg = models.DecimalField('Capacidade Peso (kg)', max_digits=12, decimal_places=3,
                                        default=Decimal('0.000'), validators=[MinValueValidator(Decimal('0.000'))])
    max_volume_m3 = models.DecimalField('Capacidade Volume (m³)', max_digits=12, decimal_places=3,
                                        default=Decimal('0.000'), validators=[MinValueValidator(Decimal('0.000'))])

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='load_plans_created')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Plano de Carga'
        verbose_name_plural = 'Planos de Carga'
        ordering = ['-planned_date', '-created_at']

    def __str__(self):
        return f"{self.name} - {self.vehicle.name}"

    @property
    def code(self):
        return f'PLC-{self.pk}'

    @property
    def total_deliveries(self) -> int:
        """Calcula dinamicamente o total de entregas."""
        from tmsapp.models import RouteCompositionDelivery
        return RouteCompositionDelivery.objects.filter(load_plan=self).count()

    @property
    def total_weight_kg(self) -> Decimal:
        """Calcula dinamicamente o peso total das entregas."""
        from tmsapp.models import RouteCompositionDelivery
        cds = RouteCompositionDelivery.objects.filter(load_plan=self).select_related('delivery')
        return sum((cd.delivery.total_weight_kg or Decimal('0.000')) for cd in cds)

    @property
    def total_volume_m3(self) -> Decimal:
        """Calcula dinamicamente o volume total das entregas."""
        from tmsapp.models import RouteCompositionDelivery
        cds = RouteCompositionDelivery.objects.filter(load_plan=self).select_related('delivery')
        return sum((cd.delivery.total_volume_m3 or Decimal('0.000')) for cd in cds)
    
    @property
    def total_value(self) -> Decimal:
        """
        Retorna o valor total (soma de price) de todas as entregas
        deste load plan.
        """
        from tmsapp.scriptApp.models.RouteComposition import RouteCompositionDelivery

        cds = RouteCompositionDelivery.objects.filter(load_plan=self).select_related('delivery')
        total = sum((cd.delivery.price or Decimal('0.00')) for cd in cds)
        if not total:
            return 0
        return total.quantize(Decimal('0.01'))

    @property
    def total_area_deliveries(self) -> int:
        """
        Retorna um QuerySet contendo todas as entregas cujo
        RouteCompositionDelivery.route_area == esta área do LoadPlan.
        """
        from tmsapp.models import Delivery
        # Primeiro, obtém a área do próprio LoadPlan (via rota -> route_area).
        if not self.route:
            return 0
        area = self.route.route_area

        # Em seguida, busca todos os Delivery ligados a RCD que têm route_area = area
        return Delivery.objects.filter(
            composition_assignments__route_area=area
        ).distinct().count()

    @property
    def total_areas(self) -> int:
        if not self.route:
            return 0
        return 1

    @property
    def is_volume_overloaded(self) -> bool:
        """Indica se o volume total excede a capacidade."""
        return self.total_volume_m3 > self.max_volume_m3
    
    @property
    def is_weight_overloaded(self) -> bool:
        """Indica se o peso total excede a capacidade."""
        return self.total_weight_kg > self.max_weight_kg

    @property
    def formatted_total_weight_kg(self) -> str:
        v = float(self.total_weight_kg)
        s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s

    @property
    def formatted_max_weight_kg(self) -> str:
        v = float(self.max_weight_kg)
        s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    
    @property
    def formatted_total_volume_m3(self) -> str:
        v = float(self.total_volume_m3)
        s = f"{v:,.2f}".replace(",", "X").replace("X", ".")
        return s

    @property
    def formatted_max_volume_m3(self) -> str:
        v = float(self.max_volume_m3)
        s = f"{v:,.2f}".replace(",", "X").replace("X", ".")
        return s
    
    @property
    def formatted_total_value(self) -> str:
        val = float(self.total_value or 0)
        s = f"{val:,.2f}"
        s = s.replace(",", "X").replace("X", ".")
        return f"{s}"


# registra no auditlog
auditlog.register(LoadPlan)