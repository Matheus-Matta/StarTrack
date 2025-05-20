from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import TemplateView
from .views import *

from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

app_name = 'tmsapp'

urlpatterns = [
  
 path('script/', include('tmsapp.scriptApp.urls')),
 path('fleet/', include('tmsapp.fleetApp.urls')),


]