import threading
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

class TaskRecord(models.Model):
    """
    Armazena vínculo entre Celery task_id e usuário, além de status e resultado/erro.
    Implementa timeout de 10s: se não houver save() nesse intervalo, marca FAIL+100%.
    """
    STATUS_PENDING  = 'pending'
    STATUS_STARTED  = 'started'
    STATUS_PROGRESS = 'progress'
    STATUS_SUCCESS  = 'success'
    STATUS_FAILURE  = 'failure'

    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pendente'),
        (STATUS_STARTED,  'Iniciada'),
        (STATUS_PROGRESS, 'Processando'),
        (STATUS_SUCCESS,  'Concluída'),
        (STATUS_FAILURE,  'Falha'),
    ]

    TIMEOUT_SECONDS = 2

    task_id    = models.CharField(max_length=255, null=True, blank=True)
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    name       = models.CharField(max_length=255, blank=True)
    porcent    = models.IntegerField(null=True, blank=True, default=0)
    status     = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    message    = models.TextField(null=True, blank=True)
    error      = models.TextField(null=True, blank=True)

    # classe guarda todos os timers ativos, pra cancelar depois
    _timers = {}

    def __str__(self):
        return f"{self.task_id} ({self.get_status_display()})"

    def _auto_fail(self):
        """
        Callback do timer: dispara se não houve save() em TIMEOUT_SECONDS.
        Força status=FAILURE, porcent=100 e grava.
        """
        # Recarrega instância
        obj = TaskRecord.objects.filter(pk=self.pk).first()
        if not obj:
            return
        # Se ainda não finalizado
        if obj.status not in (self.STATUS_SUCCESS, self.STATUS_FAILURE):
            obj.status = self.STATUS_FAILURE
            obj.porcent = 100
            obj.error = obj.error or "Timeout automático (10s) sem atualização."
            obj.save()
        # Limpa timer
        TaskRecord._timers.pop(self.pk, None)

    def _start_timer(self):
        # cancela timer anterior
        self._cancel_timer()
        t = threading.Timer(self.TIMEOUT_SECONDS, self._auto_fail)
        t.daemon = True
        t.start()
        TaskRecord._timers[self.pk] = t

    def _cancel_timer(self):
        t = TaskRecord._timers.pop(self.pk, None)
        if t:
            t.cancel()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        prev_status = None
        if not is_new:
            prev = TaskRecord.objects.get(pk=self.pk)
            prev_status = prev.status

        super().save(*args, **kwargs)

        # se for novo, já inicia o timer
        # ou se mudou de status, reinicia/cancela conforme
        if self.status in (self.STATUS_SUCCESS, self.STATUS_FAILURE):
            # encerra qualquer timer pendente
            self._cancel_timer()
        else:
            # em qualquer outro caso (novo ou status não-final), reinicia o timer
            self._start_timer()

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

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title      = models.CharField(max_length=255)
    message    = models.TextField()
    level      = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    created_at = models.DateTimeField(auto_now_add=True)
    read       = models.BooleanField(default=False)
    link       = models.URLField(null=True, blank=True)
    link_name  = models.CharField(max_length=255, null=True, blank=True)
    action     = models.CharField(max_length=255, null=True, blank=True)

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
        return level_icons.get(self.level, 'ki-solid ki-information-4')
    