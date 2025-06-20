from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import TemplateView
from .views import *
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from .views import *

app_name = 'fleetapp'

urlpatterns = [
  
    path('dashboard/', FleetDashboardView.as_view(), name='dashboard'),

    path('vehicles/', VehicleListView.as_view(), name='vehicle_list'),
    path('vehicle/create/', VehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicle/<int:pk>/update/', VehicleUpdateView.as_view(), name='vehicle_update'),
    path('vehicle/<int:pk>/disabled/', VehicleDeactivateView.as_view(), name='vehicle_deactivate'),

    path('drivers/', DriverListView.as_view(), name='driver_list'),
    path('driver/create/', DriverCreateView.as_view(), name='driver_create'),
    path('driver/<int:pk>/update/', DriverUpdateView.as_view(), name='driver_update'),
    path('driver/<int:pk>/delete/', DriverDeactivateView.as_view(), name='driver_delete'),

    path('carriers/', CarrierListView.as_view(), name='carrier_list'),
    path('carrier/create/', CarrierCreateView.as_view(), name='carrier_create'),
    path('carrier/<int:pk>/update/', CarrierUpdateView.as_view(), name='carrier_update'),
    path('carrier/<int:pk>/deactivate/', CarrierDeactivateView.as_view(), name='carrier_deactivate'),

    path('loadplan/details/<int:scripting_id>/<int:plan_id>/', loadplan_details, name='planload_drawer'),
    path('loadplan/update/', update_loadplan_delivery, name='update_loadplan_delivery'),
    path('loadplan/delete/<int:scripting_id>/<int:plan_id>/', delete_loadplan, name='delete_loadplan'),
]
