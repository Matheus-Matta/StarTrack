# fleetApp/views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from tmsapp.fleetApp.models import Driver
from tmsapp.fleetApp.forms import DriverForm
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.apps import apps
from django.forms.forms import NON_FIELD_ERRORS

class DriverListView(LoginRequiredMixin, ListView):
    model = Driver
    template_name = 'pages/fleet/driver_list.html'
    context_object_name = 'drivers'
    paginate_by = 20
    login_url = 'login'


class DriverCreateView(LoginRequiredMixin, CreateView):
    model = Driver
    form_class = DriverForm
    template_name = 'pages/fleet/driver_form.html'
    success_url = reverse_lazy('tmsapp:fleetapp:driver_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, 'Motorista cadastrado com sucesso.')
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


class DriverUpdateView(LoginRequiredMixin, UpdateView):
    model = Driver
    form_class = DriverForm
    template_name = 'pages/fleet/driver_form.html'
    success_url = reverse_lazy('tmsapp:fleetapp:driver_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, 'Motorista atualizado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        # Para cada campo com erro, exibe um toast com o verbose_name e a mensagem de erro
        for field_name, error_list in form.errors.items():
            # erros não associados a campo específico ficam em '__all__'
            if field_name == forms.NON_FIELD_ERRORS:
                for error in error_list:
                    messages.error(self.request, error)
            else:
                # pega o label (verbose_name) do campo
                label = form.fields[field_name].label
                for error in error_list:
                    messages.error(self.request, f'Campo"{label}": {error}')
        return super().form_invalid(form)


class DriverDeactivateView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request, pk):
        driver = get_object_or_404(Driver, pk=pk)
        driver.is_active = False
        driver.save()
        messages.success(request, 'Motorista desativado com sucesso.')
        return redirect('tmsapp:fleetapp:driver_list')




