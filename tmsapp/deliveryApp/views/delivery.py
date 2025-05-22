# tmsapp/delivery/views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.forms.forms import NON_FIELD_ERRORS
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from tmsapp.models import Delivery, DeliveryStatus
from tmsapp.deliveryApp.forms import DeliveryForm
from djangonotify.models import TaskRecord

from tmsapp.tasks import import_deliveries_from_sheet
import os
import tempfile

class DeliveryListView(LoginRequiredMixin, ListView):
    model = Delivery
    template_name = 'pages/delivery/delivery_list.html'
    context_object_name = 'deliveries'
    paginate_by = 20

class DeliveryCreateView(LoginRequiredMixin, CreateView):
    model = Delivery
    form_class = DeliveryForm
    template_name = 'pages/delivery/delivery_form.html'
    success_url = reverse_lazy('tmsapp:deliveryapp:delivery_list')

    def form_valid(self, form):
        messages.success(self.request, 'Entrega criada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        for field_name, error_list in form.errors.items():
            if field_name == NON_FIELD_ERRORS:
                for err in error_list:
                    messages.error(self.request, err)
            else:
                label = form.fields[field_name].label
                for err in error_list:
                    messages.error(self.request, f'Campo "{label}": {err}')
        return super().form_invalid(form)

class DeliveryUpdateView(LoginRequiredMixin, UpdateView):
    model = Delivery
    form_class = DeliveryForm
    template_name = 'pages/delivery/delivery_form.html'
    success_url = reverse_lazy('tmsapp:deliveryapp:delivery_list')

    def form_valid(self, form):
        messages.success(self.request, 'Entrega atualizada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        for field_name, error_list in form.errors.items():
            if field_name == NON_FIELD_ERRORS:
                for err in error_list:
                    messages.error(self.request, err)
            else:
                label = form.fields[field_name].label
                for err in error_list:
                    messages.error(self.request, f'Campo "{label}": {err}')
        return super().form_invalid(form)

class DeliveryCancelView(LoginRequiredMixin, View):
    """Marca uma entrega como cancelada."""
    def post(self, request, pk):
        entrega = get_object_or_404(Delivery, pk=pk)
        entrega.status = 'CANCELLED'
        entrega.is_active = False
        entrega.save()
        messages.success(request, 'Entrega excluida com sucesso.')
        return redirect('tmsapp:deliveryapp:delivery_list')



@login_required
def import_deliveries_view(request):
    """
    Página com um form de upload que dispara a task Celery para importar as entregas.
    """
    try:
        if request.method == 'POST' and request.FILES.get('file'):
            upload = request.FILES['file']
            # Cria arquivo temporário com a mesma extensão
            _, ext = os.path.splitext(upload.name)
            fd, path = tempfile.mkstemp(suffix=ext)
            try:
                with os.fdopen(fd, 'wb') as tmp:
                    for chunk in upload.chunks():
                        tmp.write(chunk)
                # dispara a task
                tkrecord = TaskRecord.objects.create(user=request.user, name='Importar entregas', status='started')
                import_deliveries_from_sheet.delay(request.user.id, tkrecord.id, path)
                messages.success(request, "Importação iniciada com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao processar arquivo: {e}")
                # limpa o temp se algo deu errado
                if os.path.exists(path):
                    os.remove(path)
    except Exception as e:
        messages.error(request, f"Erro ao processar arquivo: {e}")    
        
    return redirect(reverse_lazy('tmsapp:deliveryapp:delivery_list'))