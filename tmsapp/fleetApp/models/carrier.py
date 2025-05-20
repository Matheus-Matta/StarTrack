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
    zip_code = models.CharField('CEP', max_length=20,  blank=True, null=True)

    des_address = models.CharField('Endereço', max_length=500, null=True, blank=True, default='')
    address = models.CharField('Endereço Completo', max_length=500, null=True, blank=True, default='')


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

    def save(self, *args, **kwargs):
        # assemble full address when any component is present
        parts = []
        if self.des_address:
            parts.append(self.des_address)
        if self.street:
            parts.append(self.street)
        if self.number:
            parts[-1] = f"{parts[-1]}, {self.number}" if parts else self.number
        if self.city:
            parts.append(self.city)
        if self.state:
            parts[-1] = f"{parts[-1]}/{self.state}" if parts else self.state
        if self.zip_code:
            parts.append(self.zip_code)
        self.address = ' - '.join(parts)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


auditlog.register(Carrier)