from django.db import models
from django.core.exceptions import ValidationError
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from django.contrib.auth.models import User
from tmsapp.action import geocode_endereco

class LocationType(models.TextChoices):
    """Enumeração dos tipos de local de empresa."""
    WAREHOUSE = 'warehouse', 'Armazém'
    STORE = 'store', 'Loja'
    DISTRIBUTION_CENTER = 'distribution_center', 'Centro de Distribuição'
    HUB = 'hub', 'Hub'
    SECONDARY_WAREHOUSE = 'secondary_warehouse', 'Armazém Secundário'
    OTHER = 'other', 'Outro'


class CompanyLocation(models.Model):
    """
    Representa um endereço físico da empresa (armazém, loja, centro de distribuição, 
    pontos de saída, etc.). Gerencia geocoding automático e garante apenas um local principal.
    """
    name = models.CharField('Nome', max_length=100, db_index=True)
    type = models.CharField(
        'Tipo de Local', max_length=30,
        choices=LocationType.choices, 
        default=LocationType.OTHER,
        db_index=True
    )
    code = models.CharField(
        'Código', max_length=20, 
        unique=True, blank=True, null=True,
        help_text='Código único do local (ex: ARM001, LOJA-SP)'
    )
    
    # Endereço completo
    address = models.CharField('Endereço', max_length=255)
    number = models.CharField('Número', max_length=10, default='0')
    complement = models.CharField('Complemento', max_length=100, blank=True, null=True)
    neighborhood = models.CharField('Bairro', max_length=255, blank=True, null=True)
    city = models.CharField('Cidade', max_length=100, db_index=True)
    state = models.CharField('Estado', max_length=100, db_index=True)
    postal_code = models.CharField('CEP', max_length=20, blank=True, null=True, db_index=True)
    country = models.CharField('País', max_length=100, default='Brasil')
    
    # Coordenadas
    latitude = models.DecimalField(
        'Latitude', max_digits=9, decimal_places=6, 
        blank=True, null=True, db_index=True
    )
    longitude = models.DecimalField(
        'Longitude', max_digits=9, decimal_places=6, 
        blank=True, null=True, db_index=True
    )
    
    # Configurações operacionais
    is_active = models.BooleanField('Ativo', default=True, db_index=True)
    is_principal = models.BooleanField('Principal', default=False, db_index=True)
    is_departure_point = models.BooleanField(
        'Ponto de Saída', default=False,
        help_text='Indica se este local pode ser usado como ponto de partida para entregas'
    )
    
    # Horários de funcionamento (opcional)
    opening_time = models.TimeField('Horário de Abertura', blank=True, null=True)
    closing_time = models.TimeField('Horário de Fechamento', blank=True, null=True)
    
    # Informações de contato
    phone = models.CharField('Telefone', max_length=20, blank=True, null=True)
    email = models.EmailField('E-mail', blank=True, null=True)
    contact_person = models.CharField('Responsável', max_length=100, blank=True, null=True)
    
    # Observações
    notes = models.TextField('Observações', blank=True, null=True)

    created_at = models.DateTimeField('Data de Cadastro', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('Data de Atualização', auto_now=True)
    created_by = models.ForeignKey(
        User, verbose_name='Criado por',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='locations_created'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Local da Empresa'
        verbose_name_plural = 'Locais da Empresa'
        indexes = [
            models.Index(fields=['is_active', 'type']),
            models.Index(fields=['is_principal', 'is_active']),
            models.Index(fields=['is_departure_point', 'is_active']),
            models.Index(fields=['city', 'state']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def clean(self):
        """
        Valida que apenas um local esteja marcado como principal.
        """
        if self.is_principal:
            existing_principal = CompanyLocation.objects.filter(
                is_principal=True, is_active=True
            ).exclude(pk=self.pk)
            
            if existing_principal.exists():
                raise ValidationError('Já existe um local principal ativo definido.')
   
    @property
    def get_type(self):
        return self.type.capitalize()
    
    def full_address(self) -> str:
        """
        Monta string completa de endereço para geocodificação.
        """
        parts = [
            self.address, 
            self.number,
            self.complement,
            self.neighborhood,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ', '.join(filter(None, parts))
    
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
                    old = CompanyLocation.objects.get(pk=self.pk)
                except CompanyLocation.DoesNotExist:
                    should_geocode = True
                else:
                    # se qualquer campo de endereço mudou, refaz geocodificação
                    for field in ('address','number','postal_code','neighborhood','city','state'):
                        if getattr(old, field) != getattr(self, field):
                            should_geocode = True
                            break

        if should_geocode:
            lat, lon = geocode_endereco(
                self.address,
                self.number,
                self.postal_code,
                self.neighborhood,
                self.city,
                self.state
            )
            if lat is not None and lon is not None:
                self.latitude, self.longitude = lat, lon

        super().save(*args, **kwargs)