# tmsapp/deliveryApp/views.py

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from djangonotify.models import TaskRecord
from tmsapp.scriptApp.models import RouteComposition
from tmsapp.tasks.export_loadplan_from_sheet import export_loadplan_from_sheet
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

@login_required
def export_scripting(request, scripting_id):
    try:

        """
        Dispara uma task para exportar todas as entregas de uma composição de rota
        e retorna o ID do TaskRecord para acompanhamento.
        """
        # Verifica se a composição existe e pertence ao usuário (ou é acessível)
        comp = get_object_or_404(RouteComposition, pk=scripting_id)

        # Cria um registro de tarefa para rastrear progresso e notificações
        tk = TaskRecord.objects.create(
            user=request.user,
            name=f"Exportação de Roteiro Iniciada"
        )
        # 3) Dispara a task Celery
        export_loadplan_from_sheet.delay(
            request.user.id,
            tk.id,
            scripting_id
        )
        messages.success(request, f"Processo de exportação iniciado")
        return redirect('tmsapp:scriptapp:scripting_view', comp.id)

    except Exception as e:
        messages.error(request, f"Erro ao exportar: {str(e)}")
        return redirect('tmsapp:scriptapp:scripting_view', comp.id)