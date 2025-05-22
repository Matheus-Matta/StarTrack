from django.urls import path
from .views import djangoselect

urlpatterns = [
   path('', djangoselect, name='djangoselect'),
]

