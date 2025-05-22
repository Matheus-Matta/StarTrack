# tmsapp/crm/forms.py

from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'full_name',
            'phone',
            'email',
            'cpf',
        ]
