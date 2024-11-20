from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import WorkSchedule, Personnel
from .forms import WorkScheduleForm, PersonnelForm
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
from googleapiclient.errors import HttpError

# Путь к файлу учетных данных
GOOGLE_CREDENTIALS_FILE = settings.GOOGLE_CREDENTIALS_FILE

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Загружаем учетные данные из файла
credentials = service_account.Credentials.from_service_account_file(
    GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
)

# Создаем объект для работы с Google Sheets API
service = build('sheets', 'v4', credentials=credentials)

# Авторизация и подключение к Google Sheets
def authorize_google_sheets():
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_FILE,  # Правильное подключение к credentials
        scopes=SCOPES
    )
    service = build('sheets', 'v4', credentials=creds)
    return service


def get_schedule_from_google(schedule_url):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)

    try:
        # Извлекаем ID таблицы из URL
        spreadsheet_id = schedule_url.split('/')[5]

        # Запрос данных из таблицы
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range="A1:AF100").execute()
        values = result.get('values', [])

        return values

    except HttpError as err:
        print(f"Ошибка API Google Sheets: {err}")
        return None

# Функция для обновления данных в Google Sheets
def update_schedule_in_google(sheet_id, schedule_data):
    service = authorize_google_sheets()
    sheet = service.spreadsheets()

    # Преобразуем данные в формат для Google Sheets
    values = []
    for entry in schedule_data:
        # entry содержит список для каждой строки
        values.append(entry)

    body = {'values': values}

    try:
        # Обновляем Google Sheets
        sheet.values().update(
            spreadsheetId=sheet_id,
            range="A1:{}".format(len(values) + 1),  # Обновляем соответствующий диапазон
            valueInputOption='RAW',
            body=body
        ).execute()
    except Exception as e:
        raise RuntimeError(f"Ошибка при обновлении Google Sheets: {e}")

@login_required
def edit_schedule(request, schedule_id=None):
    if schedule_id:
        schedule = get_object_or_404(WorkSchedule, id=schedule_id)
        schedule_data = get_schedule_from_google(schedule.schedule_url)  # Получаем данные из Google Sheets
    else:
        schedule = WorkSchedule()
        schedule_data = []

    if request.method == "POST":
        form = WorkScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            schedule = form.save()

            # Обрабатываем данные расписания из формы
            # Получаем данные из формы schedule_data (включая знаки "+")
            schedule_data = request.POST.getlist('schedule_data')

            # Обновляем расписание в Google Sheets
            update_schedule_in_google(schedule.schedule_url, schedule_data)

            return redirect('schedule_list')  # Перенаправление на список расписаний после сохранения
    else:
        form = WorkScheduleForm(instance=schedule)

    return render(request, 'edit_schedule.html', {'form': form, 'schedule_id': schedule.id if schedule_id else None, 'schedule_data': schedule_data})

@login_required
def schedule_list(request):
    schedules = WorkSchedule.objects.all()
    for schedule in schedules:
        schedule_data = get_schedule_from_google(schedule.schedule_url)
        schedule.data_from_google = schedule_data  # Добавим данные из Google Sheets
        print("Полученные данные:", schedule_data)  # Для отладки, выводим данные в консоль
    return render(request, 'schedule_list.html', {'schedules': schedules})

def personnel_list(request):
    # Получить все данные о работниках
    personnel = Personnel.objects.all()
    return render(request, 'personnel_list.html', {'personnel': personnel})

@login_required
def edit_personnel(request, pk):
    # Получить работника по id
    personnel = get_object_or_404(Personnel, pk=pk)

    if request.method == "POST":
        form = PersonnelForm(request.POST, instance=personnel)
        if form.is_valid():
            form.save()
            return redirect('personnel_list')
    else:
        form = PersonnelForm(instance=personnel)

    # Now rendering the form in both POST and GET cases
    return render(request, 'edit_personnel.html', {'form': form, 'personnel': personnel})
