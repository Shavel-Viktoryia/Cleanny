from django.shortcuts import render, redirect
from .models import WorkSchedule
from .forms import WorkScheduleForm
from .google_sync import get_worksheet
from django.utils import timezone

def work_schedule_view(request):
    # Получаем расписание для работника
    schedule = WorkSchedule.objects.get(personnel=request.user.personnel)

    if request.method == "POST":
        form = WorkScheduleForm(request.POST)
        if form.is_valid():
            # Получаем доступ к Google Таблице и обновляем расписание
            worksheet = get_worksheet(schedule.schedule_url, schedule.sheet_name)

            days = {
                'MONDAY': form.cleaned_data['MONDAY'],
                'TUESDAY': form.cleaned_data['TUESDAY'],
                'WEDNESDAY': form.cleaned_data['WEDNESDAY'],
                'THURSDAY': form.cleaned_data['THURSDAY'],
                'FRIDAY': form.cleaned_data['FRIDAY'],
                'SATURDAY': form.cleaned_data['SATURDAY'],
                'SUNDAY': form.cleaned_data['SUNDAY'],
            }

            # Обновляем таблицу с помощью метода update_cell
            for row, (day, status) in enumerate(days.items(), start=2):
                worksheet.update_cell(row, 2, 'Да' if status else 'Нет')

            # Обновляем поле last_updated в модели
            schedule.last_updated = timezone.now()
            schedule.save()

            # Перенаправляем на ту же страницу после обновления
            return redirect('work_schedule_view')
    else:
        form = WorkScheduleForm()

    # Передаем текущие данные расписания и форму в шаблон
    days = {
        'MONDAY': schedule.MONDAY,
        'TUESDAY': schedule.TUESDAY,
        'WEDNESDAY': schedule.WEDNESDAY,
        'THURSDAY': schedule.THURSDAY,
        'FRIDAY': schedule.FRIDAY,
        'SATURDAY': schedule.SATURDAY,
        'SUNDAY': schedule.SUNDAY,
    }

    return render(request, 'work_schedule.html', {'form': form, 'days': days})
