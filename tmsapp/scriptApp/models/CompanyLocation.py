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
    OTHER = 'other', 'Outro'


class CompanyLocation(models.Model):
    """
    Representa um endereço físico da empresa (armazém, loja, centro de distribuição, etc.).
    Gerencia geocoding automático e garante apenas um local principal.
    """
    name = models.CharField('Nome', max_length=100)
    type = models.CharField(
        'Tipo de Local', max_length=30,
        choices=LocationType.choices, default=LocationType.OTHER
    )
    address = models.CharField('Endereço', max_length=255)
    number = models.CharField('Número', max_length=10, default='0')
    neighborhood = models.CharField('Bairro', max_length=255, blank=True, null=True)
    city = models.CharField('Cidade', max_length=100)
    state = models.CharField('Estado', max_length=100)
    zip_code = models.CharField('CEP', max_length=20, blank=True, null=True)
    country = models.CharField('País', max_length=100, default='Brasil')
    latitude = models.DecimalField('Latitude', max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField('Longitude', max_digits=9, decimal_places=6, blank=True, null=True)
    is_active = models.BooleanField('Ativo', default=True)
    is_principal = models.BooleanField('Principal', default=False)

    created_at = models.DateTimeField('Data de Cadastro', auto_now_add=True)
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

    def clean(self):
        """
        Valida que apenas um local esteja marcado como principal.
        """
        if self.is_principal and CompanyLocation.objects.filter(is_principal=True).exclude(pk=self.pk).exists():
            raise ValidationError('Já existe um local principal definido.')

    def full_address(self) -> str:
        """
        Monta string completa de endereço para geocodificação.
        """
        parts = [self.address, self.number, self.neighborhood, self.city, self.state, self.zip_code, self.country]
        return ', '.join(filter(None, parts))

    def save(self, *args, **kwargs):
        """
        Geocodifica latitude/longitude se ausentes e garante unicidade do local principal.
        """
        if not (self.latitude and self.longitude):
            lat, lon = geocode_endereco(self.full_address())
            if lat and lon:
                self.latitude, self.longitude = lat, lon

        if self.is_principal:
            CompanyLocation.objects.filter(is_principal=True).exclude(pk=self.pk).update(is_principal=False)

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_type_display()})"


auditlog.register(CompanyLocation)