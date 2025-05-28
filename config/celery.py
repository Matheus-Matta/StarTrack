from celery import Celery
import os
from celery.signals import task_prerun, task_postrun
from django.utils import timezone
import pytz

@task_prerun.connect
def activate_sao_paulo_timezone(sender=None, **kwargs):
    timezone.activate(pytz.timezone('America/Sao_Paulo'))

@task_postrun.connect
def deactivate_timezone(sender=None, **kwargs):
    timezone.deactivate()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Celery descobre tasks automaticamente nos apps
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Se quiser para DEV sempre forçar solo + debug:
if os.environ.get('ENV') == 'dev':
    app.conf.worker_pool = 'solo'
    app.conf.worker_redirect_stdouts = True
    app.conf.worker_log_color = True
    app.conf.worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
    app.conf.worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] Task %(task_name)s[%(task_id)s]: %(message)s"