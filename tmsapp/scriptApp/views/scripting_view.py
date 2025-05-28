from tmsapp.models import RouteComposition, RouteDelivery, CompanyLocation  # Sua model atualizada
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from celery.result import AsyncResult
from django.contrib import messages
import json

@login_required
def scripting_view(request, scripting_id):
    # Busca a composição de rotas pelo ID ou retorna 404
    scripting = get_object_or_404(RouteComposition, id=scripting_id)
    return render(request, 'pages/routes/scripting_view.html', {'scripting': scripting})


@login_required
def route_loading_view(request, task_id):
    result = AsyncResult(str(task_id))

    if result.state in ['SUCCESS', 'FAILURE']:
        messages.warning(request, "Essa tarefa já foi finalizada ou não existe mais.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return render(request, 'partials/loading/route_loading.html', {'task_id': task_id})