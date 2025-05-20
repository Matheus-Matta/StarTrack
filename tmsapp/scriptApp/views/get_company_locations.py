# Create your views here.
from django.http import JsonResponse
from tmsapp.models import CompanyLocation

def get_company_locations_api(request):
    data = []
    for location in CompanyLocation.objects.filter(is_active=True):
        data.append({
            "name": location.name,
            "type": location.type,
            "latitude": float(location.latitude) if location.latitude else None,
            "longitude": float(location.longitude) if location.longitude else None,
        })
    return JsonResponse(data, safe=False)

