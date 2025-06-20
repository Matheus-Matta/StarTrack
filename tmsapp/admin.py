from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from tmsapp.models import RouteArea
from .models import CompanyLocation

@admin.register(CompanyLocation)
class CompanyLocationAdmin(SimpleHistoryAdmin):
    list_display = (
        "name", "type", "city", "state", "neighborhood", "number",
        "is_principal", "is_active", "postal_code"
    )
    list_filter = ("type", "is_active", "is_principal", "state")
    search_fields = ("name", "address", "city", "postal_code", "neighborhood")
    list_editable = ("is_active", "is_principal")

    fields = (
        "name", "type", "address", "number", "neighborhood", "city", "state",
        "postal_code", "country", "latitude", "longitude", "is_principal", "is_active"
    )

@admin.register(RouteArea)
class RouteAreaAdmin(SimpleHistoryAdmin):
    list_display = (
        "name",
        "city_count",
        "neighborhood_count",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "cities", "neighborhoods")
    # list_filter agora é uma tupla
    list_filter = ("status", 'hex_color')
    readonly_fields = ("created_at", "geojson")
    history_list_display = ["created_at", "history_user"]

    fieldsets = (
        (None, {
            "fields": ("name", "hex_color")
        }),
        ("Geographic Data", {
            "fields": (
                "geojson",
                "cities",
                "neighborhoods",
                "cep_start",
                "cep_end",
            )
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at", "created_by")
        }),
    )

    def city_count(self, obj):
        return len(obj.cities)
    city_count.short_description = "Cities"

    def neighborhood_count(self, obj):
        return len(obj.neighborhoods)
    neighborhood_count.short_description = "Neighborhoods"

