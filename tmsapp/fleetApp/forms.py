from django import forms
from django.core.exceptions import ValidationError
from .models import Vehicle
from .models import Driver
from .models import Carrier
from django.utils import timezone 

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'license_plate', 'brand', 'model', 'year',
            'driver', 'carrier', 'is_outsourced',
            'max_volume_m3', 'max_weight_kg', 'status',
            'vehicle_type', 'route_area', 
        ]
    def clean(self):
        cleaned = super().clean()
        is_out = cleaned.get('is_outsourced')
        driver = cleaned.get('driver')
        carrier = cleaned.get('carrier')

        if is_out:
            # se terceirizado, carrier é obrigatório
            if not carrier:
                print('carrier', 'Marque uma transportadora para veículo terceirizado.')
                self.add_error('carrier', 'Marque uma transportadora para veículo terceirizado.')
            # driver, se existir, deve ser terceirizado também
            if driver:
                print('driver', 'O motorista deve ser terceirizado para este veículo.')
                if not driver.is_outsourced:
                    self.add_error('driver', 'O motorista deve ser terceirizado para este veículo.')
        else:
            if carrier:
                self.add_error('carrier', 'Remova transportadora para veículo interno.')

        return cleaned
        
class DriverForm(forms.ModelForm):
    
    license_expiry = forms.DateField(
        input_formats=['%d/%m/%Y'],
        required=False, 
    )

    class Meta:
        model = Driver
        fields = [
            'user', 'first_name', 'last_name',
            'license_number', 'license_category', 'license_expiry',
            'phone', 'email','is_outsourced',
            'document',
        ]
        widgets = {
            'license_expiry': forms.DateInput(attrs={'type': 'date'}),
            'document': forms.CheckboxSelectMultiple(),
        }

    def clean_license_expiry(self):
        expiry = self.cleaned_data.get('license_expiry')
        if expiry and expiry < timezone.localdate():
            raise forms.ValidationError('CNH expirada. Escolha uma data futura.')
        return expiry

    def clean(self):
        cleaned = super().clean()
        # Exemplo: se terceirizado, e-mail obrigatório
        if cleaned.get('is_outsourced') and not cleaned.get('email'):
            self.add_error('email', 'Transportador terceirizado exige e-mail de contato.')
        return cleaned


class CarrierForm(forms.ModelForm):
    class Meta:
        model = Carrier
        fields = [
            'name','phone','email','number',
            'city', 'state', 'postal_code','street',
            'description', 'cnpj',
            'document', 'neighborhood',
        ]

    def clean(self):
        cleaned = super().clean()
        contact = cleaned.get('phone', '')
        
        if not contact:
            self.add_error('phone',
                           'Informe ao menos o nome de um contato da transportadora.')

        return cleaned
