from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import WorkSchedule
from .forms import WorkScheduleForm

@login_required
def edit_schedule(request, schedule_id=None):
    if schedule_id:
        # Editing an existing schedule
        schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    else:
        # Creating a new schedule
        schedule = WorkSchedule()  # Create an empty schedule object

    if request.method == "POST":
        form = WorkScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            return redirect('schedule_list')  # Redirect to the schedule list after saving
    else:
        form = WorkScheduleForm(instance=schedule)

    return render(request, 'edit_schedule.html', {'form': form, 'schedule_id': schedule.id if schedule_id else None})

@login_required
def schedule_list(request):
    schedules = WorkSchedule.objects.all()
    return render(request, 'schedule_list.html', {'schedules': schedules})
