from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldAdmin
from simple_history.admin import SimpleHistoryAdmin
from crispy_forms.helper import FormHelper
from django.utils.translation import gettext_lazy as _
from unfold.contrib.filters.admin import RangeDateFilter
from .models import Customer
from config.unfold.admin import BaseAdmin

@admin.register(Customer)
class CustomerAdmin(BaseAdmin):
    list_display = (
        'full_name', 'cpf', 'email', 'phone', 'created_at'
    )
    search_fields = (
        'full_name', 'cpf', 'email', 'phone'
    )
    list_filter = (
        ('created_at', RangeDateFilter),  # filtro de intervalo de data
    )
    ordering = ('full_name',)
    date_hierarchy = 'created_at'
