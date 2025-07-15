from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldAdmin
from simple_history.admin import SimpleHistoryAdmin
from crispy_forms.helper import FormHelper


# Base admin class combining Unfold, SimpleHistory and Crispy Forms
class BaseAdmin(SimpleHistoryAdmin, UnfoldAdmin):
    list_filter_submit = True  # show submit button for filters

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        helper = FormHelper()
        helper.form_show_labels = True
        form.helper = helper
        return form

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

      