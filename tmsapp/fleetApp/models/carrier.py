from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .driver import Driver
from .document import Document

User = get_user_model()

class Carrier(models.Model):
    """Transportadora terceirizada, com representante ou contato obrigatório."""
    name = models.CharField('Nome da Transportadora', max_length=100, db_index=True)
    description = models.CharField('Descrição', max_length=100, blank=True, null=True, db_index=True)
    phone = models.CharField('Telefone', max_length=20, blank=True, null=True)
    email = models.EmailField('E-mail', blank=True, null=True, db_index=True)
    cnpj = models.CharField('CNPJ', max_length=20, blank=True, null=True, default='')
    street = models.CharField('Logradouro', max_length=200, blank=True, null=True)
    number = models.CharField('Número', max_length=20,  blank=True, null=True)
    city = models.CharField('Cidade', max_length=100, blank=True, null=True)
    state = models.CharField('Estado', max_length= 50, blank=True, null=True)
    postal_code = models.CharField('CEP', max_length=20,  blank=True, null=True)
    neighborhood = models.CharField('Bairro', max_length=100, blank=True, null=True)

    is_active = models.BooleanField('Ativo', default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carriers_created',
    )
    document = models.ManyToManyField(
        Document,
        verbose_name='Documentos',
        blank=True,
        related_name='documents_carrier',
        help_text='Documentos relacionados a transportadora'
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Transportadora'
        verbose_name_plural = 'Transportadoras'
        ordering = ['name']
        indexes = [models.Index(fields=['name']), models.Index(fields=['description'])]

    @property
    def full_address(self):
        parts = [self.street, self.number, self.neighborhood, self.city]
        return ', '.join(filter(None, parts))
    
    def __str__(self):
        return self.name


auditlog.register(Carrier)