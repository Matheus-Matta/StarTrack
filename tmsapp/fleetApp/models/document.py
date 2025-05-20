from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog

User = get_user_model()

class DocumentPhoto(models.Model):
    """Fotos adicionais associadas a documentos de veículo ou transportadora."""
    image = models.ImageField(
        'Foto do Documento',
        upload_to='document_photos/%Y/%m/'
    )
    caption = models.CharField(
        'Legenda', max_length=255,
        blank=True, null=True,
        help_text='Descrição opcional da foto'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Foto de Documento'
        verbose_name_plural = 'Fotos de Documento'
        ordering = ['-created_at']

    def __str__(self):
        return self.caption or f'Foto #{self.pk}'


auditlog.register(DocumentPhoto)

class Document(models.Model):
    """Documentos relacionados a veículos ou transportadoras."""
    name = models.CharField('Nome do Documento', max_length=100)
    file = models.FileField('Arquivo', upload_to='documents/%Y/%m/')
    issued_date = models.DateField('Data de Emissão')
    expiry_date = models.DateField('Data de Validade', blank=True, null=True)

    # Fotos adicionais do documento
    photos = models.ManyToManyField(
        DocumentPhoto,
        verbose_name='Fotos do Documento',
        blank=True,
        related_name='documents'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering = ['-issued_date']

    def __str__(self):
        parent = self.vehicle or self.carrier
        return f"{self.name} - {parent}"


auditlog.register(Document)
