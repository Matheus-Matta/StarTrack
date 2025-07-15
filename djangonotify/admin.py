from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesRadioFilter,
    ChoicesCheckboxFilter,
    RangeNumericListFilter,
    RangeNumericFilter,
    SingleNumericFilter,
    SliderNumericFilter,
    RangeDateFilter,
    RangeDateTimeFilter,
)
from crispy_forms.helper import FormHelper

from .models import TaskRecord, Notification
from config.unfold.admin import BaseAdmin

@admin.register(TaskRecord)
class TaskRecordAdmin(BaseAdmin):
    list_display = ('task_id', 'user', 'name', 'porcent', 'status', 'created_at', 'updated_at')
    list_filter = (
        ('status', ChoicesRadioFilter),
        ('user', ChoicesRadioFilter),
    )
    search_fields = ('task_id', 'name', 'message', 'error')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

@admin.register(Notification)
class NotificationAdmin(BaseAdmin):
    list_display = ('title', 'user', 'level', 'read', 'created_at')
    list_filter = (
        ('level', ChoicesRadioFilter),
        ('read', BooleanRadioFilter),
        ('user', ChoicesRadioFilter),
    )
    search_fields = ('title', 'message', 'link', 'link_name', 'action')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        updated = queryset.update(read=True)
        self.message_user(request, f"{updated} notificação(ões) marcadas como lidas.")
    mark_as_read.short_description = 'Marcar selecionadas como lidas'

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(read=False)
        self.message_user(request, f"{updated} notificação(ões) marcadas como não lidas.")
    mark_as_unread.short_description = 'Marcar selecionadas como não lidas'
