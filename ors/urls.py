from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import TemplateView
from .views import rota_view, visualizar_composicao_view

urlpatterns = [
    path('rota', rota_view, name='rota'),
    path('rota/<int:composicao_id>', visualizar_composicao_view, name='visualizar_rota'),
]