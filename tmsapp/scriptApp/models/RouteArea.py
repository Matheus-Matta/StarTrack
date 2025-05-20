from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from django.contrib.auth.models import User


class RouteArea(models.Model):
    """
    Define áreas geográficas por geojson, bairros, cidades e faixas de CEP.
    Calcula métricas de área e distância.
    """
    name = models.CharField('Nome', max_length=100)
    geojson = models.TextField(
        'GeoJSON',
        default=dict,
        null=True,
        blank=True,
        help_text='Texto JSON bruto; será convertido depois'
    )
    neighborhoods = models.JSONField('Bairros', default=list, blank=True)
    cities = models.JSONField('Cidades', default=list, blank=True)
    cep_start = models.JSONField('CEP Início', default=list, blank=True)
    cep_end = models.JSONField('CEP Fim', default=list, blank=True)
    areatotal = models.FloatField('Área Total (m²)', blank=True, null=True)
    kmtotal = models.FloatField('Distância Total (km)', blank=True, null=True)
    status = models.CharField(
        'Status', max_length=10,
        choices=[('active','Ativo'),('disabled','Desabilitado')],
        default='active'
    )
    # Cor hexadecimal personalizada
    hex_color = models.CharField(
        'Cor HEX', max_length=7,
        default='#0074D9',
        help_text='Código de cor hexadecimal, ex: #FF0000'
    )

    created_at = models.DateTimeField(auto_now_add=True)
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
        # 'vehicles' é o related_name da FK em Vehicle.route_area
        return self.vehicles.count()

# Registro de auditoria
auditlog.register(RouteArea)
