from django.urls import path, include
from .views import *

app_name = 'deliveryapp'

urlpatterns = [
  path('deliverys', DeliveryListView.as_view(), name='delivery_list'),
  path('delivery/create/', DeliveryCreateView.as_view(), name='delivery_create'),
  path('delivery/<int:pk>/update/', DeliveryUpdateView.as_view(), name='delivery_update'),
  path('delivery/<int:pk>/cancel/', DeliveryCancelView.as_view(), name='delivery_cancel'),
  path('delivery/import', import_deliveries_view, name='delivery_import'),
]