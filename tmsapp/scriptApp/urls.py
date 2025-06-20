from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import TemplateView
from .views import *

from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

app_name = 'scriptapp'

urlpatterns = [
  
  ####### SCRIPTING PATH 
  path(
        'scripting/create/',
        login_required(lambda request: render(request, 'pages/route.html')),
        name='create_scripting'
  ),
  # pagina de loading rotas
  path('scripting/loading/<uuid:task_id>/', route_loading_view, name='route_loading'),
  # pagina de visualizar roteiro
  path('scripting/<int:scripting_id>/', scripting_view, name='scripting_view'),
  # pegar todas as localizações da empresa
  path('scripting/get_company_locations', get_company_locations_api, name='get_company_locations'), 
  # criar rotas
  path('scripting/create_routes', create_scripting, name='create_routes'),
  # pegar todas as rotas e composiçoes
  path('scripting/<int:scripting_id>/routes/', get_routes_scripting, name='get_routes_scripting'),
  # altera status do roteiro
  path('scripting/<int:scripting_id>/change_status/<str:new_status>/', update_composition_status, name='update_scripting_status'),
  # adiciona carga no roteiro
  path('scripting/<int:scripting_id>/add_load/', add_load_to_composition, name='add_load_to_composition'),
  # recalcular roteiro e suas rotas
  path('scripting/<int:scripting_id>/recalculate/', redistribute_composition, name='redistribute_composition'),

  
  
  ####### ROUTE PATH 
  path('route/create/',  create_routearea, name='create_routearea'),
  path('route/edit/<int:route_id>/', edit_routearea, name='edit_routearea'),
  path('route/delete/<int:route_id>/', delete_routearea, name='delete_routearea'),
  path('routes/', list_routearea, name='route'),
  path('route/<int:route_id>/', route_view, name='route_view'),


]