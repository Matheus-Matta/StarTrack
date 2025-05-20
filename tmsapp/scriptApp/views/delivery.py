# tmsapp/delivery/views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.forms.forms import NON_FIELD_ERRORS

from tmsapp.models import Delivery, DeliveryStatus
from tmsapp.scriptApp.forms import DeliveryForm

class DeliveryListView(LoginRequiredMixin, ListView):
    model = Delivery
    template_name = 'pages/delivery/delivery_list.html'
    context_object_name = 'deliveries'
    paginate_by = 20
    login_url = 'login'

class DeliveryCreateView(LoginRequiredMixin, CreateView):
    model = Delivery
    form_class = DeliveryForm
    template_name = 'pages/delivery/delivery_form.html'
    success_url = reverse_lazy('tmsapp:scriptapp:delivery_list')
    login_url = 'login'

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
    success_url = reverse_lazy('tmsapp:scriptapp:delivery_list')
    login_url = 'login'

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
    login_url = 'login'

    def post(self, request, pk):
        entrega = get_object_or_404(Delivery, pk=pk)
        entrega.status = DeliveryStatus.CANCELLED
        entrega.save()
        messages.success(request, 'Entrega cancelada com sucesso.')
        return redirect('tmsapp:scriptapp:delivery_list')
