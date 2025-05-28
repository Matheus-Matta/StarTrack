from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import os
from django.conf import settings
import uuid
from tmsapp.tasks import create_script_perso_task
from datetime import datetime
from djangonotify.models import TaskRecord
@login_required
def create_scripting(request):
    if request.method == "POST":
        try:
            # 1) Campos do POST
            sp_router = request.POST.get("sp_router")                     
            priority_router = request.POST.get("priority_router") == "on" 

            date_range = request.POST.get("date_range", "")
            start_str, end_str = date_range.split(" - ")

            start_date = datetime.strptime(start_str, "%d/%m/%Y").date()
            end_date   = datetime.strptime(end_str,   "%d/%m/%Y").date()

            # 2) formata como ISO string (YYYY-MM-DD)
            start = start_date.strftime("%Y-%m-%d")
            end  = end_date.  strftime("%Y-%m-%d")

            if sp_router == "route_perso":
                tkrecord = TaskRecord.objects.create(user=request.user, name='Criando roterização', status='started')
                create_script_perso_task.delay(request.user.id, tkrecord.id, start, end)
                messages.info(request, f"Processo roterização iniciado - {start} - {end}")
            else:
                messages.error(request, f"Roterização por cidade indisponível para o momento.")

            return redirect("tmsapp:scriptapp:create_scripting")

        except Exception as e:
            tkrecord.status = 'failure'
            tkrecord.save()
            messages.error(request, f"Erro ao iniciar o processo: {e}")
            return redirect("tmsapp:scriptapp:create_scripting")

    return redirect("tmsapp:scriptapp:create_scripting")

