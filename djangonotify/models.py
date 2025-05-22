from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class TaskRecord(models.Model):
    """
    Armazena o vínculo entre Celery task_id e usuário,
    além de status e resultado/erro para visualização.
    """
    task_id    = models.CharField(max_length=255, null=True, blank=True)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    name       = models.CharField(max_length=255, blank=True)  # opcional: nome legível da task
    porcent    = models.IntegerField(max_length=100, null=True, blank=True, default=0)
    status     = models.CharField(
        max_length=20,
        choices=[
            ('PENDING','Pendente'),
            ('STARTED','Iniciada'),
            ('PROGRESS','Processando'),
            ('SUCCESS','Concluída'),
            ('FAILURE','Falha'),
        ],
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    message    = models.TextField(null=True, blank=True)
    error      = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.task_id} ({self.get_status_display()})"


class Notification(models.Model):
    """
    Notificações genéricas que podem ser enviadas a usuários via WebSocket.
    """
    LEVEL_CHOICES = [
        ('info','Info'),
        ('warning','Warning'),
        ('danger','Error'),
        ('success','Success'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title      = models.CharField(max_length=255)
    message    = models.TextField()
    level      = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    created_at = models.DateTimeField(auto_now_add=True)
    read       = models.BooleanField(default=False)
    link       = models.URLField(null=True, blank=True)
    def __str__(self):
        return f"[{self.level}] {self.title}"
    @property
    def level_icon(self):
        level_icons = {
            'info': 'ki-solid ki-information-4',
            'warning': 'ki-solid ki-information',
            'danger': 'ki-solid ki-cross-circle',
            'success': 'ki-solid ki-verify',
        }
        return level_icons.get(self.level, 'ℹ️')
    