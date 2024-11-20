from django import forms
from .models import WorkSchedule, Personnel

class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = ['personnel', 'schedule_url']  # Только нужные поля

    schedule_data = forms.JSONField(widget=forms.Textarea, required=False)  # Поле для данных расписания

class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = ['telegram_id', 'nickname', 'phone_number', 'email', 'hours_worked_today', 'hours_worked_week']
