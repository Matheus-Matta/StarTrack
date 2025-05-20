from django.contrib.auth.models import User
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from decouple import config

@receiver(post_migrate)
def create_default_admin(sender, **kwargs):
    username = config('DEFAULT_ADMIN_USERNAME', default='admin')
    password = config('DEFAULT_ADMIN_PASSWORD', default='123')
    email = config('DEFAULT_ADMIN_EMAIL', default='admin@example.com')

    if not User.objects.filter(username=username).exists():
        print(f'🛠️ Criando usuário admin padrão: {username}')
        User.objects.create_superuser(username=username, email=email, password=password)
