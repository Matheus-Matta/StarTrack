from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.contrib import messages
from django.shortcuts import redirect

from tmsapp.models import RouteComposition, RouteCompositionStatus

@login_required
@require_POST
def update_composition_status(request, scripting_id: int, new_status: str):
    try:
        """
        Atualiza o status de uma RouteComposition
        """
        if request.method != 'POST':
            messages.error(request, 'Erro ao atualizar o status da composição. metodo inválido.')
            return redirect('tmsapp:scriptapp:scripting_view', scripting_id)
        
        composition = get_object_or_404(RouteComposition, pk=scripting_id)

        if new_status == 'delete':
            composition.delete()
            messages.success(request, "Composição excluida com sucesso.")
            return redirect('tmsapp:scriptapp:create_scripting')

        # Valida o novo status
        if new_status not in RouteCompositionStatus.values:
            messages.error(
                request,
                f"Status inválido. Valores permitidos: {', '.join(RouteCompositionStatus.values)}"
            )
            print(f"[change status] Status inválido. Valores permitidos: {', '.join(RouteCompositionStatus.values)}")
            return redirect('tmsapp:scriptapp:scripting_view', scripting_id)

        with transaction.atomic():
            composition.status = new_status
            composition.save()

        messages.success(request, "Status da composição e das entregas atualizados com sucesso.")
        return redirect('tmsapp:scriptapp:scripting_view', scripting_id)

    except Exception as e:
        print(f'[change status] erro:{str(e)}')
        messages.error(request, f"Erro ao atualizar o status da composição: {str(e)}")
        return redirect('tmsapp:scriptapp:scripting_view', scripting_id)
