from django.db import models
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from django.contrib.auth.models import User
from tmsapp.action import geocode_endereco

class DeliveryStatus(models.TextChoices):
    PENDING     = 'pending',     'Pendente'
    SCHEDULED   = 'scheduled',   'Agendada'
    IN_TRANSIT  = 'in_transit',  'Em Trânsito'
    DELIVERED   = 'delivered',   'Entregue'
    FAILED      = 'failed',      'Falha na Entrega'
    CANCELLED   = 'cancelled',   'Cancelada'

class Delivery(models.Model):
    """
    Registro de entrega de pedidos a clientes, com dados de geocodificação automática.
    """
    customer_name = models.CharField('Nome do Cliente', max_length=255)
    order_number = models.CharField('Número do Pedido', max_length=50)
    street = models.CharField('Rua', max_length=255)
    number = models.CharField('Número', max_length=20)
    neighborhood = models.CharField('Bairro', max_length=100)
    city = models.CharField('Município', max_length=100)
    state = models.CharField('Estado', max_length=50)
    postal_code = models.CharField('CEP', max_length=20, blank=True, null=True)
    latitude = models.DecimalField('Latitude', max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField('Longitude', max_digits=9, decimal_places=6, blank=True, null=True)
    phone = models.CharField('Telefone', max_length=20, blank=True, null=True)
    cpf = models.CharField('CPF', max_length=20, blank=True, null=True)
    observation = models.TextField('Observação', blank=True, null=True)
    reference = models.CharField('Ponto de Referência', max_length=255, blank=True, null=True)
    is_check = models.BooleanField('Marcado no Mapa', default=False)

    status = models.CharField(
        'Status',
        max_length=15,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
        help_text='Situação atual da entrega'
    )

    created_at = models.DateTimeField('Data de Cadastro', auto_now_add=True)
    updated_at = models.DateTimeField('Data de Atualização', auto_now=True)
    created_by = models.ForeignKey(
        User, verbose_name='Criado por',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deliveries_created'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Entrega'
        verbose_name_plural = 'Entregas'

    @property
    def full_address(self) -> str:
        """
        Monta endereço completo para geocodificação.
        """
        parts = [self.street, self.number, self.neighborhood, self.city, self.state, self.postal_code, 'Brasil']
        return ', '.join(filter(None, parts))

    def save(self, *args, **kwargs):
        """
        Autogeocodifica coordenadas se ausentes.
        """
        if not (self.latitude and self.longitude):
            lat, lon = geocode_endereco(self.full_address)
            if lat and lon:
                self.latitude, self.longitude = lat, lon

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.customer_name} - Pedido {self.order_number}"


auditlog.register(Delivery)