
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from .Route import Route
from auditlog.registry import auditlog

class RouteType(models.TextChoices):
    CITY    = 'city',   'Rotas por cidade'
    UNIQUE  = 'unique', 'Rota única'
    CUSTOM  = 'custom', 'Rota Personalizada'   # nova opção
    OTHER   = 'other',  'Outro'


class RouteComposition(models.Model):
    """
    Agrupa múltiplas rotas em uma composição, com cálculos agregados.
    """
    name = models.CharField('Nome', max_length=100)
    type = models.CharField('Tipo de Rota', max_length=30,  choices=RouteType.choices, default='other')
    routes = models.ManyToManyField(Route, related_name='compositions', verbose_name='Rotas')
    observations = models.TextField('Observações', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, verbose_name='Criado por', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='route_compositions_created'
    )
    
    is_active = models.BooleanField('Ativo', default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Composição de Rota'
        verbose_name_plural = 'Composições de Rotas'

    def __str__(self) -> str:
        return self.name

    @property
    def total_deliveries(self) -> int:
        """Soma total de paradas (deliveries) entre as rotas agregadas."""
        return self.routes.aggregate(models.Sum('stops'))['stops__sum'] or 0

    @property
    def total_distance(self) -> float:
        """Distância acumulada de todas as rotas."""
        return round(self.routes.aggregate(models.Sum('distance_km'))['distance_km__sum'] or 0, 2)

    @property
    def total_time(self) -> str:
        """Retorna duração da composição formatada (base na maior rota)."""
        max_minutes = self.routes.aggregate(models.Max('time_min'))['time_min__max']
        if not max_minutes:
            return 'Sem dados'
        total_seconds = int(max_minutes * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = [f"{hours}h" if hours else '', f"{minutes}m" if minutes else '', f"{seconds}s" if seconds else '']
        return ' '.join(filter(None, parts))

auditlog.register(RouteComposition)
