from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import TemplateView
from .views import DashboardView
from django.shortcuts import redirect

app_name = 'homeapp'

urlpatterns = [
    path('', lambda request: redirect('homeapp:dashboard', permanent=False), name='home'),
    path('dashboard', DashboardView, name='dashboard'),
]