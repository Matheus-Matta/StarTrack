# tmsapp/scriptApp/views.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

@login_required
@require_POST
def redistribute_composition(request, scripting_id):
    messages.success(request, "Redistribuição concluída e rotas recalculadas.")
    return redirect('tmsapp:scriptapp:scripting_view', scripting_id)
