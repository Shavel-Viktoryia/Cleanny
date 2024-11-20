from django import forms

class WorkScheduleForm(forms.Form):
    MONDAY = forms.BooleanField(required=False, label="Понедельник")
    TUESDAY = forms.BooleanField(required=False, label="Вторник")
    WEDNESDAY = forms.BooleanField(required=False, label="Среда")
    THURSDAY = forms.BooleanField(required=False, label="Четверг")
    FRIDAY = forms.BooleanField(required=False, label="Пятница")
    SATURDAY = forms.BooleanField(required=False, label="Суббота")
    SUNDAY = forms.BooleanField(required=False, label="Воскресенье")
