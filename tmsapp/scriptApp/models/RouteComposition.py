from django.db import models
from django.contrib.auth.models import User
from django.db import transaction
from django.core.cache import cache
from simple_history.models import HistoricalRecords
from .Route import Route
from tmsapp.deliveryApp.models import Delivery
from auditlog.registry import auditlog
from tmsapp.fleetApp.models import LoadPlan
class RouteType(models.TextChoices):
    CITY    = 'city',   'Rotas por cidade'
    UNIQUE  = 'unique', 'Rota única'
    CUSTOM  = 'custom', 'Rota Personalizada'
    OTHER   = 'other',  'Outro'


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('route_composition', 'delivery')
        ordering = ['sequence']
        verbose_name = 'Entrega da Composição de Rota'
        verbose_name_plural = 'Entregas da Composição de Rota'
        indexes = [
            models.Index(fields=['route_composition', 'sequence']),
            models.Index(fields=['load_plan', 'delivery']),
            models.Index(fields=['delivery', 'load_plan']),
        ]

    def __str__(self) -> str:
        load_info = f" (Carga: {self.load_plan.name})" if self.load_plan else " (Fora de carga)"
        return f"{self.route_composition.name} - {self.delivery}{load_info}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalida cache da composição pai
        self.route_composition.invalidate_cache()


auditlog.register(RouteComposition)
auditlog.register(RouteCompositionDelivery)
