from django import forms
from .models import WorkSchedule

class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = ['personnel', 'schedule_url']  # Поля, которые нужно редактировать
        widgets = {
            'schedule_url': forms.TextInput(attrs={'placeholder': 'Введите ссылку на Google Таблицу'}),
        }
