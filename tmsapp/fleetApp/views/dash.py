# fleetApp/views.py
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.db.models import Sum
from tmsapp.fleetApp.models import Driver, Vehicle, Carrier, Route  # importe seu modelo de rota

class FleetDashboardView(LoginRequiredMixin, View):
    template_name = 'pages/fleet/dashboard.html'
    login_url = 'login'

    def get(self, request, *args, **kwargs):
        # 1) Veículos em trânsito (por ora fixo)
        in_transit = 0

        # 2) Motoristas, veículos e transportadoras ativas
        drivers  = Driver.objects.filter(is_active=True)
        vehicles = Vehicle.objects.filter(status='active')
        carriers = Carrier.objects.all()

        # 3) Top 5 veículos por capacidade de volume (m³)
        top_vehicles = (
            vehicles
            .order_by('-capacity_volume')
            .values('license_plate', 'capacity_volume')[:5]
        )

        context = {
            # cartão "em trânsito"
            'routes': {
                'in_transit': in_transit,
            },
            # agrupando a frota
            'frota': {
                'drivers':  drivers,
                'vehicles': vehicles,
                'carriers': carriers,
            },
            # dados para o gráfico de capacidade
            'chart': {
                'labels': [v.license_plate for v in vehicles],
                'volume_data': [float(v.capacity_volume) for v in vehicles],
                'weight_data': [float(v.capacity_weight) for v in vehicles],
                'title':  'Top 5 Veículos por Capacidade (m³)',
            }
        }
        return render(request, self.template_name, context)
