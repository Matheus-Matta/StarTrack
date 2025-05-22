# tmsapp/deliveryApp/forms.py
from django import forms
from .models import Delivery, DeliveryStatus
from crmapp.models import Customer


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = [
            'customer', 'order_number','street', 'number',
            'neighborhood', 'city', 'state', 'postal_code',
            'observation', 'reference',
        ]