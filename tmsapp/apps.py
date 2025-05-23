from django.apps import AppConfig


class TmsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tmsapp'

    def ready(self):
        from . import tasks  # <- Importa o pacote tasks ao iniciar

