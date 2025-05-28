# models/base.py (crie este arquivo)
from django.db import models
from django.conf import settings
from django.utils import timezone

class BaseModel(models.Model):
    """Model base que salva todos os timestamps usando o TIME_ZONE do settings"""
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        # Puxa o timezone padrão do settings
        tz = timezone.get_default_timezone()

        for field in self._meta.fields:
            if isinstance(field, models.DateTimeField):
                valor = getattr(self, field.name)

                # Se é auto_now ou auto_now_add (nova instância), abastece com agora no TZ do settings
                if field.auto_now or (field.auto_now_add and not self.pk):
                    now_aware = timezone.now()
                    # Converte para o timezone configurado
                    now_local = timezone.localtime(now_aware, tz)
                    # Armazena como naive, removendo tzinfo
                    setattr(self, field.name, now_local.replace(tzinfo=None))

                # Se já tem valor e é aware, converte para o timezone configurado
                elif valor is not None and hasattr(valor, 'tzinfo') and valor.tzinfo:
                    local_val = valor.astimezone(tz)
                    setattr(self, field.name, local_val.replace(tzinfo=None))

        super().save(*args, **kwargs)
