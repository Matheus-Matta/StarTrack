import re
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from django.contrib.auth.models import User


class RouteArea(models.Model):
    """
    Define áreas geográficas por geojson, bairros, cidades e faixas de CEP.
    Calcula métricas de área e distância e gerencia veículos associados.
    """
    name = models.CharField('Nome', max_length=100, db_index=True)
    geojson = models.TextField(
        'GeoJSON',
        default=dict,
        null=True,
        blank=True,
        help_text='Texto JSON bruto do polígono da área'
    )
    neighborhoods = models.JSONField('Bairros', default=list, blank=True)
    cities = models.JSONField('Cidades', default=list, blank=True)
    cep_start = models.JSONField('CEP Início', default=list, blank=True)
    cep_end = models.JSONField('CEP Fim', default=list, blank=True)
    areatotal = models.FloatField('Área Total (m²)', blank=True, null=True)
    kmtotal = models.FloatField('Distância Total (km)', blank=True, null=True)
    
    status = models.CharField(
        'Status', max_length=10,
        choices=[('active', 'Ativo'), ('disabled', 'Desabilitado')],
        default='active',
        db_index=True
    )
    is_active = models.BooleanField('Ativo', default=True, db_index=True)
    
    # Cor hexadecimal personalizada
    hex_color = models.CharField(
        'Cor HEX', max_length=7,
        default='#0074D9',
        help_text='Código de cor hexadecimal, ex: #FF0000'
    )
    
    # Ponto de saída padrão para esta área
    departure_location = models.ForeignKey(
        'CompanyLocation',
        verbose_name='Ponto de Saída',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='route_areas_departure',
        help_text='Local de partida padrão para rotas desta área'
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, verbose_name='Criado por',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='route_areas_created'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Área de Rota'
        verbose_name_plural = 'Áreas de Rotas'
        indexes = [
            models.Index(fields=['is_active', 'status']),
            models.Index(fields=['-created_at', 'is_active']),
            models.Index(fields=['departure_location', 'is_active']),
        ]

    def __str__(self) -> str:
        return self.name or ""
    
    def clean(self):
        super().clean()
        if self.hex_color and not re.match(r'^#[0-9A-Fa-f]{6}$', self.hex_color):
            raise ValidationError({'hex_color': 'Formato de cor inválido. Use #RRGGBB.'})

    @property
    def cep_ranges(self) -> list[tuple]:
        """Retorna faixas de CEP emparelhadas."""
        return list(zip(self.cep_start, self.cep_end))
    
    @property
    def vehicle_count(self) -> int:
        """Conta veículos ativos associados a esta área."""
        return self.vehicles.filter(is_active=True).count()
    
    @property
    def active_vehicles(self):
        """Retorna queryset de veículos ativos desta área."""
        return self.vehicles.filter(is_active=True)
    
    def get_departure_point(self):
        """
        Retorna o ponto de saída para esta área.
        Prioriza: departure_location específica > CompanyLocation principal
        """
        if self.departure_location:
            return self.departure_location
        
        # Fallback para local principal da empresa
        from .CompanyLocation import CompanyLocation
        return CompanyLocation.objects.filter(
            is_principal=True, 
            is_active=True
        ).first()
    
    def calculate_total_capacity(self):
        """Calcula capacidade total dos veículos desta área."""
        vehicles = self.active_vehicles
        return {
            'total_weight_kg': sum(v.max_weight_kg for v in vehicles),
            'total_volume_m3': sum(v.max_volume_m3 for v in vehicles),
            'vehicle_count': vehicles.count()
        }


auditlog.register(RouteArea)