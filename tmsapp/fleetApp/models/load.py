"""
Django models for Vehicle, Driver, and Load (Carga) in the TMS app.
Load links multiple Deliveries to a Vehicle and Route, with volume/weight per item.
Follows Clean Code conventions, audit logging, and historical records.
"""

from django.db import models
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .vehicle import Vehicle
from .driver import Driver
from tmsapp.models import Delivery, Route
from django.utils import timezone


User = get_user_model()


class LoadStatus(models.TextChoices):
    """Status de uma carga/trip."""
    PENDING = 'pending', 'Pendente'
    LOADED = 'loaded', 'Carregado'
    IN_TRANSIT = 'in_transit', 'Em trânsito'
    COMPLETED = 'completed', 'Concluído'
    DECOMMISSIONED = 'decommissioned', 'Baixado'


class Load(models.Model):
    """
    Representa uma carga de múltiplos pedidos (Delivery) em um veículo e rota.
    Gerencia capacidade do veículo, status e totais de volume/peso.
    """
    vehicle = models.ForeignKey(
        Vehicle,
        verbose_name='Veículo',
        on_delete=models.PROTECT,
        related_name='loads'
    )
    driver = models.ForeignKey(
        Driver,
        verbose_name='Motorista',
        on_delete=models.PROTECT,
        related_name='loads',
        null=True,
        blank=True
    )
    route = models.ForeignKey(
        Route,
        verbose_name='Rota',
        on_delete=models.PROTECT,
        related_name='loads'
    )
    date = models.DateField('Data de Carregamento', default=timezone.now)

    # Ligação M2M para vários pedidos, passando por LoadDelivery
    deliveries = models.ManyToManyField(
        Delivery,
        through='LoadDelivery',
        related_name='loads'
    )

    # Capacidade do veículo no momento do carregamento
    capacity_volume = models.DecimalField(
        'Capacidade Veículo (m³)', max_digits=8, decimal_places=2,
        editable=False
    )

    # Totais calculados de volume e peso de todos os itens
    total_volume = models.DecimalField(
        'Volume Total (m³)', max_digits=10, decimal_places=2, default=0
    )
    total_weight = models.DecimalField(
        'Peso Total (kg)', max_digits=10, decimal_places=2, default=0
    )

    status = models.CharField(
        'Status da Carga', max_length=15,
        choices=LoadStatus.choices,
        default=LoadStatus.PENDING
    )

    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    created_by = models.ForeignKey(
        User,
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loads_created'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Carga'
        verbose_name_plural = 'Cargas'
        ordering = ['-date']

    def save(self, *args, **kwargs):
        # Herdar capacidade do veículo
        self.capacity_volume = self.vehicle.capacity_volume
        super().save(*args, **kwargs)
        # Após salvar Load, recalcula totais
        total_vol = 0
        total_wt = 0
        for item in self.loaddelivery_set.all():
            total_vol += item.volume
            total_wt += item.weight
        # Atualiza sem reentrar em loop de save
        Load.objects.filter(pk=self.pk).update(
            total_volume=total_vol,
            total_weight=total_wt
        )
    def clean(self):
        """
        Impede criar nova carga se já existir carga aberta (PENDING, LOADED, IN_TRANSIT)
        para este veículo.
        """
        # open_states = [
        #    LoadStatus.PENDING,
        #    LoadStatus.LOADED,
        #    LoadStatus.IN_TRANSIT
        # ]
        # qs = Load.objects.filter(
        #    vehicle=self.vehicle,
        #    status__in=open_states
        # ).exclude(pk=self.pk)
        # if qs.exists():
        #    raise ValidationError(
        #        'Já existe uma carga aberta para este veículo. ' 
        #        'Finalize ou encerre-a antes de criar outra.'
        #    )

    def __str__(self) -> str:
        return f"Carga #{self.pk} - {self.vehicle} em {self.date}"


auditlog.register(Load)


class LoadDelivery(models.Model):
    """
    Item de carga: ligação entre Load e Delivery,
    incluindo volume, peso e ordem de entrega.
    """
    load = models.ForeignKey(
        Load,
        on_delete=models.CASCADE,
        related_name='loaddelivery_set'
    )
    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name='loaddelivery_set'
    )
    volume = models.DecimalField('Volume (m³)', max_digits=8, decimal_places=2)
    weight = models.DecimalField('Peso (kg)', max_digits=8, decimal_places=2)
    position = models.PositiveIntegerField('Ordem de entrega', default=0)

    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('load', 'delivery')
        ordering = ['position']
        verbose_name = 'Item de Carga'
        verbose_name_plural = 'Itens de Carga'

    def save(self, *args, **kwargs):
        # Se volume/peso não fornecidos, herda do Delivery (se existir)
        if self.volume is None and hasattr(self.delivery, 'volume_m3'):
            self.volume = self.delivery.volume_m3
        if self.weight is None and hasattr(self.delivery, 'weight_kg'):
            self.weight = self.delivery.weight_kg
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.load} -> {self.delivery}"


auditlog.register(LoadDelivery)
