from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import TemplateView
from django.shortcuts import redirect
from .views import djangotables

urlpatterns = [
   path('', djangotables, name='djangotables'),
]

