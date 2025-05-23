# views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from tmsapp.fleetApp.models import Vehicle
from tmsapp.fleetApp.forms import VehicleForm
from django import forms  
from django.forms.forms import NON_FIELD_ERRORS

class VehicleListView(LoginRequiredMixin, ListView):
    """Exibe lista de veículos, somente para usuários autenticados"""
    model = Vehicle
    template_name = 'pages/fleet/vehicle_list.html'
    context_object_name = 'vehicles'
    paginate_by = 20

class VehicleCreateView(LoginRequiredMixin, CreateView):
    """Cria novo veículo, acesso restrito a usuários autenticados"""
    model = Vehicle
    form_class = VehicleForm
    template_name = 'pages/fleet/vehicle_form.html'
    success_url = reverse_lazy('tmsapp:fleetapp:vehicle_list')

    def form_valid(self, form):
        messages.success(self.request, 'Veículo criado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        # Para cada campo com erro, exibe um toast com o verbose_name e a mensagem de erro
        for field_name, error_list in form.errors.items():
            # erros não associados a campo específico ficam em '__all__'
            if field_name == NON_FIELD_ERRORS:
                for error in error_list:
                    messages.error(self.request, error)
            else:
                # pega o label (verbose_name) do campo
                label = form.fields[field_name].label
                for error in error_list:
                    messages.error(self.request, f'Campo"{label}": {error}')
        return super().form_invalid(form)


class VehicleUpdateView(LoginRequiredMixin, UpdateView):
    """Edita veículo existente, acesso restrito"""
    model = Vehicle
    form_class = VehicleForm
    template_name = 'pages/fleet/vehicle_form.html'
    success_url = reverse_lazy('tmsapp:fleetapp:vehicle_list')

    def form_valid(self, form):
        messages.success(self.request, 'Veículo atualizado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        # Para cada campo com erro, exibe um toast com o verbose_name e a mensagem de erro
        for field_name, error_list in form.errors.items():
            # erros não associados a campo específico ficam em '__all__'
            if field_name == NON_FIELD_ERRORS:
                for error in error_list:
                    messages.error(self.request, error)
            else:
                # pega o label (verbose_name) do campo
                label = form.fields[field_name].label
                for error in error_list:
                    messages.error(self.request, f'Campo"{label}": {error}')
        return super().form_invalid(form)

class VehicleDeactivateView(LoginRequiredMixin, View):
    """Soft-delete: desativa veículo (acesso restrito)"""
    
    def post(self, request, pk):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        vehicle.status = 'DECOMMISSIONED'
        vehicle.is_active = False
        vehicle.save()
        messages.success(request, 'Veículo desativado com sucesso.')
        return redirect('tmsapp:fleetapp:vehicle_list')