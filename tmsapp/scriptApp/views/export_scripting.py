# tmsapp/deliveryApp/views.py

import logging
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError

from djangonotify.models import TaskRecord
from tmsapp.scriptApp.models import RouteComposition
from tmsapp.models import LoadPlan, RouteCompositionDelivery
from tmsapp.tasks.export_loadplan_from_sheet import (
    export_loadplan_from_sheet,
    export_loadplan_by_loadplan,
)

# Configuração do logger para capturar erros
logger = logging.getLogger(__name__)

# Constantes para mensagens
MESSAGES = {
    'EXPORT_STARTED': "Processo de exportação iniciado com sucesso.",
    'EXPORT_ERROR': "Erro ao iniciar processo de exportação. Tente novamente.",
    'COMPOSITION_NOT_FOUND': "Composição de rota não encontrada para este load plan.",
    'TASK_ERROR': "Erro ao criar tarefa de exportação.",
    'GENERIC_ERROR': "Erro interno do sistema. Contate o administrador.",
}

# URLs padrão para redirecionamento
DEFAULT_REDIRECT_URL = 'tmsapp:scriptapp:scripting_view'


def _create_task_record(user, task_name):
    """
    Cria um registro de tarefa de forma segura.
    
    Args:
        user: Usuário que está executando a tarefa
        task_name: Nome da tarefa a ser criada
        
    Returns:
        TaskRecord: Instância da tarefa criada
        
    Raises:
        ValidationError: Se houver erro na criação da tarefa
    """
    try:
        with transaction.atomic():
            task_record = TaskRecord.objects.create(
                user=user,
                status='started',
                name=task_name
            )
            logger.info(f"Tarefa criada com sucesso: {task_name} para usuário {user.id}")
            return task_record
    except Exception as e:
        logger.error(f"Erro ao criar tarefa '{task_name}': {str(e)}")
        raise ValidationError(MESSAGES['TASK_ERROR'])


def _get_composition_redirect_url(composition_id):
    """
    Retorna a URL de redirecionamento para a visualização da composição.
    
    Args:
        composition_id: ID da composição
        
    Returns:
        str: URL para redirecionamento
    """
    try:
        return ('tmsapp:scriptapp:scripting_view', composition_id)
    except Exception:
        logger.warning(f"Erro ao gerar URL para composição {composition_id}")
        return DEFAULT_REDIRECT_URL


@login_required
def export_scripting(request, scripting_id):
    """
    Dispara uma tarefa assíncrona para exportar todas as entregas de uma composição de rota.
    
    Args:
        request: HttpRequest objeto
        scripting_id: ID da composição de rota (RouteComposition)
        
    Returns:
        HttpResponse: Redirecionamento para a view da composição
    """
    try:
        # Busca a composição de rota ou retorna 404
        composition = get_object_or_404(RouteComposition, pk=scripting_id)
        
        # Cria o registro da tarefa
        task_name = f"Exportação de Composição {composition.id}"
        task_record = _create_task_record(request.user, task_name)
        
        # Dispara a tarefa assíncrona
        export_loadplan_from_sheet.delay(
            request.user.id,
            task_record.id,
            composition.id
        )
        
        # Adiciona mensagem de sucesso
        messages.success(request, MESSAGES['EXPORT_STARTED'])
        logger.info(f"Exportação iniciada para composição {composition.id} pelo usuário {request.user.id}")
        
        # Redireciona para a view da composição
        return redirect('tmsapp:scriptapp:scripting_view', composition.id)
        
    except Http404:
        # Erro 404 é re-lançado para o Django tratar
        raise
        
    except ValidationError as e:
        # Erro de validação na criação da tarefa
        messages.error(request, str(e))
        logger.error(f"Erro de validação na exportação da composição {scripting_id}: {str(e)}")
        return redirect(DEFAULT_REDIRECT_URL, composition.id)
        
    except Exception as e:
        # Captura qualquer outro erro não previsto
        messages.error(request, MESSAGES['GENERIC_ERROR'])
        logger.error(f"Erro inesperado na exportação da composição {scripting_id}: {str(e)}")
        return redirect(DEFAULT_REDIRECT_URL, composition.id)


@login_required
def export_scripting_by_loadplan(request, loadplan_id):
    """
    Dispara uma tarefa assíncrona para exportar apenas as entregas de um loadplan específico.
    Após a exportação, redireciona para a view da composição correspondente.
    
    Args:
        request: HttpRequest objeto
        loadplan_id: ID do plano de carga (LoadPlan)
        
    Returns:
        HttpResponse: Redirecionamento para a view da composição
    """
    try:
        # Busca o loadplan ou retorna 404
        load_plan = get_object_or_404(LoadPlan, pk=loadplan_id)
        
        # Busca a composição associada ao loadplan
        route_composition_delivery = RouteCompositionDelivery.objects.filter(
            load_plan_id=loadplan_id
        ).select_related('route_composition').first()
        
        if not route_composition_delivery:
            messages.error(request, MESSAGES['COMPOSITION_NOT_FOUND'])
            logger.warning(f"Nenhuma composição encontrada para loadplan {loadplan_id}")
            raise Http404("Nenhuma composição encontrada para este load plan.")
        
        # Obtém a composição
        composition = route_composition_delivery.route_composition
        if not composition:
            composition = get_object_or_404(RouteComposition, pk=route_composition_delivery.route_composition_id)
        
        # Cria o registro da tarefa
        task_name = f"Exportação de Carga {load_plan.id}"
        task_record = _create_task_record(request.user, task_name)
        
        # Dispara a tarefa assíncrona
        export_loadplan_by_loadplan.delay(
            request.user.id,
            task_record.id,
            load_plan.id
        )
        
        # Adiciona mensagem de sucesso
        messages.success(request, MESSAGES['EXPORT_STARTED'])
        logger.info(f"Exportação iniciada para loadplan {load_plan.id} pelo usuário {request.user.id}")
        
        # Redireciona para a view da composição
        return redirect('tmsapp:scriptapp:scripting_view', composition.id)
        
    except Http404:
        # Erro 404 é re-lançado para o Django tratar
        raise
        
    except ValidationError as e:
        # Erro de validação na criação da tarefa
        messages.error(request, str(e))
        logger.error(f"Erro de validação na exportação do loadplan {loadplan_id}: {str(e)}")
        return redirect(DEFAULT_REDIRECT_URL, composition.id)
        
    except Exception as e:
        # Captura qualquer outro erro não previsto
        messages.error(request, MESSAGES['GENERIC_ERROR'])
        logger.error(f"Erro inesperado na exportação do loadplan {loadplan_id}: {str(e)}")
        return redirect(DEFAULT_REDIRECT_URL, composition.id)