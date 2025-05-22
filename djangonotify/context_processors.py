# djangonotify/context_processors.py
from django.core.paginator import Paginator
from .models import Notification, TaskRecord
def notifications_and_tasks(request):
    """
    Injeta nas views => 
      notifications_page  : página de notificações (10 itens por vez)
      tasks_page          : página de tarefas (10 itens por vez)
    """
    user = request.user
    if not user.is_authenticated:
        return {
            'notifications': None,
            'tasks':         None,
        }

    # consulta ordenada por data de criação
    notifs = Notification.objects.filter(user=user).order_by('-created_at')
    tasks = (
        TaskRecord.objects
        .filter(user=user, task_id__isnull=False)      # não-nulo
        .exclude(task_id='')                            # não-vazio, se você armazena '' inicialmente
        .order_by('-created_at')
    )


    # paginadores de 10 em 10
    notif_page = Paginator(notifs, 7).get_page(1)
    task_page  = Paginator(tasks,  7).get_page(1)
    return {
        'notifications': notif_page,
        'tasks':         task_page,
    }
