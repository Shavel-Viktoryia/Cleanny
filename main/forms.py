from django import forms
from .models import (WorkSchedule, Personnel, Order, Service, Customer, Equipment,
                     DailyInventory, EquipmentUsage)

class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = ['personnel', 'schedule_url']  # Только нужные поля

    schedule_data = forms.JSONField(widget=forms.Textarea, required=False)  # Поле для данных расписания

class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = ['telegram_id', 'nickname', 'phone_number', 'email', 'hours_worked_today', 'hours_worked_week']

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer', 'services', 'personnel', 'scheduled_time', 'status', 'travel_time_minutes', 'total_price', 'total_duration_minutes']
        widgets = {
            'scheduled_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'price', 'duration_minutes', 'is_quantity_modifiable']

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'nickname', 'telegram_id', 'contact_number', 'email']

class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ['name', 'type', 'quantity', 'last_restocked']
        widgets = {
            'last_restocked': forms.DateInput(attrs={'type': 'date'}),
        }

class DailyInventoryForm(forms.ModelForm):
    class Meta:
        model = DailyInventory
        fields = ['date', 'personnel', 'status']

class EquipmentUsageForm(forms.ModelForm):
    class Meta:
        model = EquipmentUsage
        fields = ['daily_inventory', 'equipment', 'quantity_used', 'returned_quantity']