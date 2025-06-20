# Route.py (mantido conforme solicitado, com melhorias de performance)
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from tmsapp.deliveryApp.models import Delivery
from auditlog.registry import auditlog

class Route(models.Model):
    """
    Representa rota de entregas, com distância, tempo e geometrias.
    """
    name = models.CharField('Nome', max_length=100, blank=True, null=True, db_index=True)
    color = models.CharField('Cor', max_length=7, default='#3498db')
    stops = models.PositiveIntegerField('Paradas', blank=True, null=True)
    distance_km = models.FloatField('Distância (km)', blank=True, null=True)
    time_min = models.FloatField('Tempo (minutos)', blank=True, null=True)
    geojson = models.JSONField('GeoJSON', blank=True, null=True)
    points = models.JSONField('Points', blank=True, null=True)

    route_area = models.ForeignKey(
        'RouteArea',
        verbose_name='Área de Rota',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='routes',
        db_index=True
    )

    deliveries = models.ManyToManyField(
        Delivery, 
        through='RouteDelivery', 
        related_name='routes', 
        verbose_name='Entregas'
    )

    is_active = models.BooleanField('Ativo', default=True, db_index=True)

    created_at = models.DateTimeField('Criado em', auto_now_add=True, db_index=True)
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
        indexes = [
            models.Index(fields=['-created_at', 'is_active']),
            models.Index(fields=['route_area', 'is_active']),
            models.Index(fields=['distance_km', 'time_min']),
        ]

    def __str__(self) -> str:
        return self.name or 'Rota sem nome'


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
        indexes = [
            models.Index(fields=['route', 'position']),
            models.Index(fields=['delivery', 'route']),
        ]

    def __str__(self) -> str:
        return f"{self.route} - {self.delivery} (Pos {self.position})"


auditlog.register(Route)
auditlog.register(RouteDelivery)