from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .vehicle import Vehicle
from django.utils import timezone

User = get_user_model()

class Inspection(models.Model):
    """Checklist de inspeção periódica de veículos."""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='inspections')
    date = models.DateField('Data da Inspeção', default=timezone.now)
    status = models.BooleanField('Aprovado', default=True)
    notes = models.TextField('Observações', blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='inspections_created'
    )

    class Meta:
        verbose_name = 'Inspeção'
        verbose_name_plural = 'Inspeções'
        ordering = ['-date']

    def __str__(self):
        return f"Inspeção {self.vehicle} em {self.date}: {'OK' if self.status else 'Falha'}"


auditlog.register(Inspection)