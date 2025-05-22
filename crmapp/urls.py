# tmsapp/crm/urls.py

from django.urls import path
from .views import (
    CustomerListView,
    CustomerCreateView,
    CustomerUpdateView,
    CustomerDeleteView,
)

app_name = 'crmapp'

urlpatterns = [
    # Lista de clientes
    path(
        'customers',
        CustomerListView.as_view(),
        name='customer_list'
    ),

    # Criar novo cliente
    path(
        'customer/create/',
        CustomerCreateView.as_view(),
        name='customer_create'
    ),

    # Editar um cliente existente
    path(
        'customer/<int:pk>/update/',
        CustomerUpdateView.as_view(),
        name='customer_update'
    ),

    # Excluir um cliente
    path(
        'customer/<int:pk>/delete/',
        CustomerDeleteView.as_view(),
        name='customer_delete'
    ),
]
