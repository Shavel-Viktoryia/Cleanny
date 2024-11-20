from django import forms
from .models import WorkSchedule

class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = ['personnel', 'schedule_url']  # Только нужные поля

    schedule_data = forms.JSONField(widget=forms.Textarea, required=False)  # Поле для данных расписания
