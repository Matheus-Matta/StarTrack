from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from .Delivery import Delivery
from auditlog.registry import auditlog

class Route(models.Model):
    """
    Representa rota de entregas, com distância, tempo e geometrias.
    """
    name = models.CharField('Nome', max_length=100, blank=True, null=True)
    color = models.CharField('Cor', max_length=7, default='#3498db')
    stops = models.PositiveIntegerField('Paradas')
    distance_km = models.FloatField('Distância (km)')
    time_min = models.FloatField('Tempo (minutos)')
    geojson = models.JSONField('GeoJSON')
    points = models.JSONField('Points')

    deliveries = models.ManyToManyField(
        Delivery, through='RouteDelivery', related_name='routes', verbose_name='Entregas'
    )

    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    created_by = models.ForeignKey(
        User, verbose_name='Criado por',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='routes_created'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Rota'
        verbose_name_plural = 'Rotas'

    def __str__(self) -> str:
        return self.name or 'Rota sem nome'


auditlog.register(Route)


class RouteDelivery(models.Model):
    """
    Associação entre Rota e Entrega, define a ordem de parada.
    """
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE)
    position = models.PositiveIntegerField('Posição na Rota')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('route', 'delivery')
        ordering = ['position']
        verbose_name = 'Parada de Rota'
        verbose_name_plural = 'Paradas de Rota'

    def __str__(self) -> str:
        return f"{self.route} - {self.delivery} (Pos {self.position})"


auditlog.register(RouteDelivery)