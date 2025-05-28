import pytz
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

class SaoPauloTimezoneMiddleware(MiddlewareMixin):
    """Middleware que força todos os timestamps para São Paulo"""
    
    def process_request(self, request):
        # Define o timezone para São Paulo em todas as requisições
        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        timezone.activate(sao_paulo_tz)
    
    def process_response(self, request, response):
        timezone.deactivate()
        return response
