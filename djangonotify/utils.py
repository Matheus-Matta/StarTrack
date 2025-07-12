import json
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import TaskRecord, Notification

def send_progress(task_id: str, user_id: int, message: str, percent: int, status: str = 'progress', extra: dict=None):
    """
    Atualiza TaskRecord e envia via WebSocket progresso ou erro.
    Grupos: "task_{task_id}_{user_id}"
    """
    # 1) Atualiza o registro no banco
    tr, _ = TaskRecord.objects.get_or_create(task_id=task_id, defaults={'user_id':user_id})
    tr.status = status
    tr.updated_at = tr.updated_at  # atualiza timestamp
    tr.porcent = percent
    tr.message = message
    tr.save(update_fields=['status','porcent','message','updated_at'])

    # 2) Prepara payload
    payload = {
        'id': tr.id,
        'name': tr.name,
        'task_id': task_id,
        'message': message,
        'percent': percent,
        'status': status,
    }
    if extra:
        payload.update(extra)

    text = json.dumps(payload)
    group = f"tasks_{user_id}"
    async_to_sync(get_channel_layer().group_send)(
        group,
        {'type':'send.progress', 'text': text}
    )

def send_notification(
    user_id: int,
    title: str,
    message: str,
    level: str = 'info',
    link: str | None = None,
    link_name: str | None = None,
    action: str | None = None
) -> Notification:
    """
    Cria uma Notification e envia via WebSocket para o grupo alerts_{user_id}.
    """
    # 1) Cria no banco
    notif = Notification.objects.create(
        user_id=user_id,
        title=title,
        message=message,
        level=level,
        link=link,
        link_name=link_name,
        action=action
    )

    # 2) Prepara payload
    payload = {
        'id':         notif.id,
        'title':      notif.title,
        'message':    notif.message,
        'level':      notif.level,
        'level_icon': notif.level_icon,
        'created_at': notif.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
    }
    if link:
        payload['link'] = link
    if link_name:
        payload['link_name'] = link_name
    if action:
        payload['action'] = action

    # 3) Dispara via Channels
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"alerts_{user_id}",
        {
            'type': 'send.alert', 
            'text': json.dumps(payload)
        }
    )

    return notif