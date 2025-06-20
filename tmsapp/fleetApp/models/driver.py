from django.db import models
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .document import Document
from django.utils import timezone
from django.core.exceptions import ValidationError

User = get_user_model()

class DriverLicenseCategory(models.TextChoices):
    """Categorias de CNH suportadas."""
    A = 'Categoria A', 'Categoria A'
    B = 'Categoria B', 'Categoria B'
    C = 'Categoria C', 'Categoria C'
    D = 'Categoria D', 'Categoria D'
    E = 'Categoria E', 'Categoria E'
    AB = 'Categoria AB', 'Categoria AB'

class Driver(models.Model):
    """Motorista cadastrado na frota."""
    user = models.OneToOneField(User, on_delete=models.CASCADE,  null=True, blank=True, related_name='driver_profile', default=None)
    first_name = models.CharField('Nome', max_length=50)
    last_name = models.CharField('Sobrenome', max_length=50)
    license_number = models.CharField('CNH', max_length=20, null=True, blank=True, unique=True, db_index=True)
    license_category = models.CharField(
        'Categoria da CNH',
        max_length=30,
        null=True,
         blank=True,
        choices=DriverLicenseCategory.choices,
        help_text='Categoria habilitada do motorista'
    )
    license_expiry = models.DateField('Validade da CNH', null=True, blank=True,)
    phone = models.CharField('Telefone', max_length=20, blank=True, null=True, db_index=True)
    email = models.EmailField('E-mail', blank=True, null=True, db_index=True)

    is_active = models.BooleanField('Ativo', default=True)
    is_outsourced = models.BooleanField('Terceirizado', default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='drivers_created'
    )

    document = models.ManyToManyField(
        Document,
        verbose_name='Documentos',
        blank=True,
        related_name='documents_drive',
        help_text='Documentos relacionados ao motorista'
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Motorista'
        verbose_name_plural = 'Motoristas'
        ordering = ['last_name', 'first_name']
        indexes = [models.Index(fields=['license_number']), models.Index(fields=['email'])]

    def clean(self):
        if self.license_expiry:
            if self.license_expiry < timezone.localdate():
                raise ValidationError('CNH expirada.')

    @property
    def is_license_valid(self) -> bool:
        return self.license_expiry >= timezone.localdate()

    def __str__(self):  
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

auditlog.register(Driver)

