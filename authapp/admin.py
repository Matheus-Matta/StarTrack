import threading
from django.contrib import admin
from django.urls import reverse_lazy
from unfold.admin import ModelAdmin as UnfoldAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesRadioFilter,
)
from crispy_forms.helper import FormHelper
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType

from config.unfold.admin import BaseAdmin
# Base admin class combining Unfold theme, history and crispy forms

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, BaseAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'group_list',
        'is_active', 'is_staff', 'is_superuser'
    )
    list_editable = ('email', 'first_name', 'last_name')
    list_filter = (
        ('is_active', BooleanRadioFilter),
        ('is_staff', BooleanRadioFilter),
        ('is_superuser', BooleanRadioFilter),
        ('groups', ChoicesRadioFilter),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Informações Pessoais', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Permissões', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        ('Datas Importantes', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'first_name', 'last_name', 'email',
                'password1', 'password2', 'groups'
            ),
        }),
    )

    def group_list(self, obj):
        return ", ".join(obj.groups.values_list('name', flat=True))
    group_list.short_description = 'Grupos'


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, BaseAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)
    filter_horizontal = ('permissions',)


@admin.register(Permission)
class PermissionAdmin(BaseAdmin):
    list_display = ('name', 'codename', 'content_type')
    list_filter = (('content_type', ChoicesRadioFilter),)
    search_fields = ('name', 'codename')
    ordering = ('content_type__app_label', 'content_type__model', 'codename')


@admin.register(ContentType)
class ContentTypeAdmin(BaseAdmin):
    list_display = ('app_label', 'model')
    search_fields = ('app_label', 'model')
    ordering = ('app_label', 'model')
