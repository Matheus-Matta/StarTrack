from django.contrib import admin
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesRadioFilter,
    ChoicesCheckboxFilter,
    RangeNumericListFilter,
    RangeNumericFilter,
    SingleNumericFilter,
    SliderNumericFilter,
    RangeDateFilter,
)
from crispy_forms.helper import FormHelper
from .models import (
    CompanyLocation, Route, RouteDelivery,
    RouteArea, RouteComposition, RouteCompositionDelivery,
    Carrier, Driver, LoadPlan, VehicleAssignment,
    Vehicle, Delivery
)
from config.unfold.admin import BaseAdmin

@admin.register(CompanyLocation)
class CompanyLocationAdmin(BaseAdmin):
    list_display = (
        'name', 'type', 'code', 'city', 'state',
        'is_active', 'is_principal', 'is_departure_point'
    )
    list_filter = (
        ('type', ChoicesRadioFilter),
        ('is_active', BooleanRadioFilter),
        ('is_principal', ChoicesCheckboxFilter),
        ('is_departure_point', ChoicesCheckboxFilter),
    )
    search_fields = ('name', 'code', 'address', 'city', 'state', 'postal_code')
    ordering = ('name',)

class RouteDeliveryInline(admin.TabularInline):
    model = RouteDelivery
    extra = 0
    fields = ('delivery', 'position')
    ordering = ('position',)

@admin.register(Route)
class RouteAdmin(BaseAdmin):
    inlines = [RouteDeliveryInline]
    list_display = (
        'name', 'route_area', 'stops', 'distance_km',
        'time_min', 'is_active', 'created_at'
    )
    list_filter = (
        ('route_area', ChoicesRadioFilter),
        ('is_active', BooleanRadioFilter),
    )
    search_fields = ('name',)
    list_select_related = ('route_area',)

@admin.register(RouteDelivery)
class RouteDeliveryAdmin(BaseAdmin):
    list_display = ('route', 'delivery', 'position')
    list_filter = (('route', ChoicesRadioFilter),)
    ordering = ('route', 'position')
    search_fields = ('route__name', 'delivery__id')

@admin.register(RouteArea)
class RouteAreaAdmin(BaseAdmin):
    list_display = (
        'name', 'status', 'is_active',
        'departure_location', 'areatotal', 'kmtotal'
    )
    list_filter = (
        ('status', ChoicesRadioFilter),
        ('is_active', BooleanRadioFilter),
    )
    search_fields = ('name',)
    list_select_related = ('departure_location',)
    fieldsets = (
        (None, {
            'fields': (
                'name', 'status', 'is_active',
                'hex_color', 'departure_location'
            )
        }),
        ('Geografia', {
            'fields': (
                'geojson', 'neighborhoods', 'cities',
                'cep_start', 'cep_end', 'areatotal', 'kmtotal'
            )
        }),
    )

class RouteCompositionDeliveryInline(admin.TabularInline):
    model = RouteCompositionDelivery
    extra = 0
    fields = ('delivery', 'load_plan', 'route_area', 'sequence')
    ordering = ('sequence',)

@admin.register(RouteComposition)
class RouteCompositionAdmin(BaseAdmin):
    inlines = [RouteCompositionDeliveryInline]
    filter_horizontal = ('load_plans_direct',)
    list_display = (
        'name', 'status', 'total_deliveries',
        'deliveries_with_loadplan', 'deliveries_without_loadplan',
        'total_load_plans'
    )
    list_filter = (
        ('status', ChoicesRadioFilter),
        ('is_active', BooleanRadioFilter),
    )
    search_fields = ('name',)
    date_hierarchy = 'created_at'

@admin.register(RouteCompositionDelivery)
class RouteCompositionDeliveryAdmin(BaseAdmin):
    list_display = (
        'route_composition', 'delivery',
        'load_plan', 'sequence'
    )
    list_filter = (
        ('route_composition', ChoicesRadioFilter),
        ('load_plan', ChoicesRadioFilter),
    )
    ordering = ('route_composition', 'sequence')
    search_fields = ('route_composition__name', 'delivery__id')

@admin.register(Carrier)
class CarrierAdmin(BaseAdmin):
    list_display = (
        'name', 'description', 'cnpj', 'phone', 'email', 'is_active'
    )
    list_filter = (('is_active', BooleanRadioFilter),)
    search_fields = ('name', 'cnpj', 'email', 'description')
    ordering = ('name',)

class VehicleAssignmentInline(admin.TabularInline):
    model = VehicleAssignment
    extra = 0
    fields = ('driver', 'start_date', 'end_date')
    ordering = ('-start_date',)

@admin.register(Driver)
class DriverAdmin(BaseAdmin):
    list_display = (
        'full_name', 'license_number', 'license_category',
        'license_expiry', 'phone', 'email', 'is_active', 'is_outsourced'
    )
    list_filter = (
        ('license_category', ChoicesRadioFilter),
        ('is_active', BooleanRadioFilter),
        ('is_outsourced', BooleanRadioFilter),
    )
    search_fields = ('first_name', 'last_name', 'license_number', 'email')
    ordering = ('last_name', 'first_name')
    inlines = [VehicleAssignmentInline]

class LoadPlanInline(admin.TabularInline):
    model = LoadPlan
    extra = 0
    fields = ('name', 'vehicle', 'planned_date', 'status')
    ordering = ('-planned_date',)

@admin.register(Vehicle)
class VehicleAdmin(BaseAdmin):
    list_display = (
        'license_plate', 'brand', 'model', 'year', 'route_area',
        'driver', 'carrier', 'status', 'is_outsourced', 'is_active'
    )
    list_filter = (
        ('status', ChoicesRadioFilter),
        ('is_outsourced', BooleanRadioFilter),
        ('is_active', BooleanRadioFilter),
        ('route_area', ChoicesRadioFilter),
    )
    search_fields = ('license_plate', 'brand', 'model')
    ordering = ('license_plate',)
    inlines = [VehicleAssignmentInline]
    list_select_related = ('route_area', 'driver', 'carrier')

@admin.register(LoadPlan)
class LoadPlanAdmin(BaseAdmin):
    list_display = (
        'name', 'route', 'vehicle', 'planned_date', 'status',
        'max_weight_kg', 'max_volume_m3'
    )
    list_filter = (
        ('status', ChoicesRadioFilter),
        ('planned_date', RangeDateFilter),
        ('vehicle__brand', ChoicesRadioFilter),
    )
    search_fields = ('name', 'route__name', 'vehicle__license_plate')
    ordering = ('-planned_date',)
    list_select_related = ('route', 'vehicle')

@admin.register(VehicleAssignment)
class VehicleAssignmentAdmin(BaseAdmin):
    list_display = ('driver', 'vehicle', 'start_date', 'end_date')
    list_filter = (
        ('driver', ChoicesRadioFilter),
        ('vehicle', ChoicesRadioFilter),
    )
    search_fields = (
        'driver__first_name', 'driver__last_name', 'vehicle__license_plate'
    )
    ordering = ('-start_date',)

@admin.register(Delivery)
class DeliveryAdmin(BaseAdmin):
    list_display = (
        'order_number', 'customer_name', 'date_delivery', 'status', 'is_active'
    )
    list_filter = (
        ('status', ChoicesRadioFilter),
        ('date_delivery', RangeDateFilter), 
        ('is_active', BooleanRadioFilter),
    )
    search_fields = (
        'order_number',
        'customer__first_name',
        'customer__last_name'
    )
    ordering = ('-date_delivery',)
    list_select_related = ('customer',)
