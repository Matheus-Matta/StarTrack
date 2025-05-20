# tmsapp/deliveryApp/forms.py
from django import forms
from .models import Delivery, DeliveryStatus

class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = [
            'customer_name', 'order_number',
            'street', 'number', 'neighborhood', 'city', 'state', 'postal_code',
            'phone', 'cpf',
            'observation', 'reference', 'is_check',
            'status',
        ]
        widgets = {
            'postal_code': forms.TextInput(attrs={'placeholder': '00000-000'}),
            'cpf':         forms.TextInput(attrs={'placeholder': '000.000.000-00'}),
            'status':     forms.Select(),
        }
        help_texts = {
            'is_check': 'Marque se quiser que apareça destacado no mapa.',
        }