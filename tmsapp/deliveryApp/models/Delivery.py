from django.db import models
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from django.contrib.auth.models import User
from tmsapp.action import geocode_endereco
from crmapp.models import Customer

class DeliveryStatus(models.TextChoices):
    PENDING     = 'pending',     'pendente'
    SCHEDULED   = 'scheduled',   'agendada'
    IN_TRANSIT  = 'in-transit',  'em Trânsito'
    DELIVERED   = 'delivered',   'entregue'
    FAILED      = 'failed',      'falha na Entrega'
    CANCELLED   = 'cancelled',   'cancelada'

class Delivery(models.Model):
    """
    Registro de entrega de pedidos a clientes, com dados de geocodificação automática.
    """
    order_number = models.CharField('Número do Pedido', max_length=50)

    street = models.CharField('Rua', max_length=255)
    number = models.CharField('Número', max_length=20)
    neighborhood = models.CharField('Bairro', max_length=100)
    city = models.CharField('Município', max_length=100)
    state = models.CharField('Estado', max_length=50)
    postal_code = models.CharField('CEP', max_length=20, blank=True, null=True)
    observation = models.TextField('Observação', blank=True, null=True)
    reference = models.CharField('Ponto de Referência', max_length=255, blank=True, null=True)
    filial = models.CharField('Filial', max_length=10, blank=True, null=True)

    latitude = models.DecimalField('Latitude', max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField('Longitude', max_digits=9, decimal_places=6, blank=True, null=True)

    status = models.CharField(
        'Status',
        max_length=15,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
        help_text='Situação atual da entrega'
    )

    customer = models.ForeignKey(
        Customer,  verbose_name='Cliente',
        on_delete=models.PROTECT,
        related_name='deliveries',
        default=None, null=True, blank=True
    )
    
    is_active = models.BooleanField('Ativo', default=True)

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
    
    @property
    def status_display(self) -> str:
        # chama o método gerado pelo Django
        return self.get_status_display()
    

    def save(self, *args, **kwargs):
        # decidir se deve geocodificar
        should_geocode = False

        # 1) se não havia coords antes, sempre geocodifica
        if not (self.latitude and self.longitude):
            should_geocode = True
        else:
            # 2) caso exista no banco, buscar antigo e comparar campos de endereço
            if self.pk:
                try:
                    old = Delivery.objects.get(pk=self.pk)
                except Delivery.DoesNotExist:
                    should_geocode = True
                else:
                    # se qualquer campo de endereço mudou, refaz geocodificação
                    for field in ('street','number','postal_code','neighborhood','city','state'):
                        if getattr(old, field) != getattr(self, field):
                            should_geocode = True
                            break

        if should_geocode:
            lat, lon = geocode_endereco(
                self.street,
                self.number,
                self.postal_code,
                self.neighborhood,
                self.city,
                self.state
            )
            if lat is not None and lon is not None:
                self.latitude, self.longitude = lat, lon

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Pedido {self.order_number}"


auditlog.register(Delivery)
