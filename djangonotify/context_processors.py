# djangonotify/context_processors.py
from django.core.paginator import Paginator
from .models import Notification, TaskRecord
def notifications_and_tasks(request):
    user = request.user
    if not user.is_authenticated:
        return {}

    # 1) Busca todas as notificações em ordem decrescente de criação
    all_notifs = Notification.objects.filter(user=user).order_by('-created_at')

    # 2) Separa não-lidas e as 5 mais recentes lidas
    unread_qs = all_notifs.filter(read=False)
    read_qs   = all_notifs.filter(read=True)[:10]

    # 3) Combina numa única lista: primeiro todas não-lidas, depois as 5 lidas
    #    (é importante converter para list antes de concatenar)
    unread_list = list(unread_qs)
    read_list   = list(read_qs)
    notifications = unread_list + read_list

    # 4) Pagina as tarefas normalmente
    tasks_qs = TaskRecord.objects.filter(user=user).order_by('-created_at')
    task_page = Paginator(tasks_qs, 10).get_page(request.GET.get('task_page'))
    return {
        'notifications':     notifications,
        'has_unread':        unread_qs.exists(),
        'tasks':             task_page,
    }
