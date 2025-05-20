# fleetApp/views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django import forms
from tmsapp.fleetApp.models import Carrier
from tmsapp.fleetApp.forms import CarrierForm  # supondo que exista
from django.forms.forms import NON_FIELD_ERRORS
  

class CarrierListView(LoginRequiredMixin, ListView):
    model = Carrier
    template_name = 'pages/fleet/carrier_list.html'
    context_object_name = 'carriers'
    paginate_by = 20
    login_url = 'login'


class CarrierCreateView(LoginRequiredMixin, CreateView):
    model = Carrier
    form_class = CarrierForm
    template_name = 'pages/fleet/carrier_form.html'
    success_url = reverse_lazy('tmsapp:fleetapp:carrier_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, 'Transportadora criada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        # Para cada campo com erro, exibe toast com o verbose_name + mensagem
        for field_name, errors in form.errors.items():
            if field_name == NON_FIELD_ERRORS:
                for err in errors:
                    messages.error(self.request, err)
            else:
                label = form.fields[field_name].label
                for err in errors:
                    messages.error(self.request, f'Campo "{label}": {err}')
        return super().form_invalid(form)


class CarrierUpdateView(LoginRequiredMixin, UpdateView):
    model = Carrier
    form_class = CarrierForm
    template_name = 'pages/fleet/carrier_form.html'
    success_url = reverse_lazy('tmsapp:fleetapp:carrier_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, 'Transportadora atualizada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        for field_name, errors in form.errors.items():
            if field_name == NON_FIELD_ERRORS:
                for err in errors:
                    messages.error(self.request, err)
            else:
                label = form.fields[field_name].label
                for err in errors:
                    messages.error(self.request, f'Campo "{label}": {err}')
        return super().form_invalid(form)


class CarrierDeactivateView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request, pk):
        carrier = get_object_or_404(Carrier, pk=pk)
        carrier.delete()  # ou marque como inativo
        messages.success(request, 'Transportadora removida com sucesso.')
        return redirect('tmsapp:fleetapp:carrier_list')
