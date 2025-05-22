# tmsapp/crm/models.py
from django.db import models
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog

User = get_user_model()

class Customer(models.Model):
    """
    Dados de cliente para CRM.
    """
    full_name    = models.CharField('Nome Completo', max_length=255)
    phone        = models.CharField('Telefone', max_length=20, blank=True, null=True)
    email        = models.EmailField('E-mail', blank=True, null=True, db_index=True)
    cpf          = models.CharField('CPF', max_length=20, blank=True, db_index=True, null=True, unique=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    created_by   = models.ForeignKey(
        User, verbose_name='Criado por',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='clients_created'
    )

    history      = HistoricalRecords()

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering     = ['full_name']
        indexes      = [models.Index(fields=['cpf']), models.Index(fields=['email'])]

    def __str__(self):
        return self.full_name

# registra auditoria
auditlog.register(Customer)
