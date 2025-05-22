# tmsapp/crm/views.py

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.forms.forms import NON_FIELD_ERRORS

from crmapp.models import Customer
from crmapp.forms import CustomerForm


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'pages/crm/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20
    login_url = 'login'


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'pages/crm/customer_form.html'
    success_url = reverse_lazy('crmapp:customer_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, 'Cliente criado com sucesso.')
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


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'pages/crm/customer_form.html'
    success_url = reverse_lazy('crmapp:customer_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, 'Cliente atualizado com sucesso.')
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


class CustomerDeleteView(LoginRequiredMixin, DeleteView):
    model = Customer
    template_name = 'pages/crm/customer_confirm_delete.html'
    success_url = reverse_lazy('crmapp:customer_list')
    login_url = 'login'

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Cliente excluído com sucesso.')
        return super().delete(request, *args, **kwargs)
