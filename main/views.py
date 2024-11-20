from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import WorkSchedule, Personnel
from .forms import WorkScheduleForm, PersonnelForm
from .models import (Order, Service, Customer, Equipment, DailyInventory,
                     Admin, MonthlyStatistics, EquipmentUsage)
from .forms import (OrderForm, ServiceForm, CustomerForm,
                    PersonnelForm, EquipmentForm, WorkScheduleForm,
                    DailyInventoryForm, EquipmentUsageForm)
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.auth.transport.requests import Request
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

    # Авторизация с помощью учетных данных
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    try:
        # Извлекаем ID таблицы из URL
        spreadsheet_id = schedule_url.split('/')[5]

        # Создаем сервисный объект для работы с Google Sheets API
        service = build('sheets', 'v4', credentials=creds)

        # Запрос данных из таблицы
        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range="A1:AF100").execute()
        values = result.get('values', [])

        # Преобразуем данные для удобного отображения
        if values:
            header = values[0]  # Первая строка - заголовки (дни недели)
            data = values[1:]  # Остальные строки - данные расписания
            return {'header': header, 'data': data}
        return {'header': [], 'data': []}

    except Exception as err:
        print(f"Ошибка при получении данных: {err}")
        return None

# Функция для обновления данных в Google Sheets
def update_schedule_in_google(sheet_id, schedule_data):
    service = authorize_google_sheets()
    sheet = service.spreadsheets()

    # Преобразуем данные в формат для Google Sheets
    values = []
    for entry in schedule_data:
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

def order_list(request):
    orders = Order.objects.all()
    return render(request, 'order_list.html', {'orders': orders})

def create_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('order_list')  # После создания перенаправляем на список заказов
    else:
        form = OrderForm()
    return render(request, 'create_order.html', {'form': form})

def edit_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            return redirect('order_list')  # После редактирования перенаправляем на список заказов
    else:
        form = OrderForm(instance=order)
    return render(request, 'edit_order.html', {'form': form})

def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        order.delete()
        return redirect('order_list')  # После удаления перенаправляем на список заказов
    return render(request, 'delete_order.html', {'order': order})

# Представление для просмотра инвентаря
def manage_inventory(request):
    daily_inventory_list = DailyInventory.objects.all()
    context = {
        'daily_inventory': daily_inventory_list,
    }
    return render(request, 'manage_inventory.html', context)

# Представление для редактирования инвентаря
def edit_inventory(request, inventory_id):
    inventory = get_object_or_404(DailyInventory, pk=inventory_id)
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=inventory)
        if form.is_valid():
            form.save()
            return redirect('manage_inventory')
    else:
        form = EquipmentForm(instance=inventory)

    context = {
        'form': form,
        'inventory': inventory,
    }
    return render(request, 'edit_inventory.html', context)

# Добавить услугу
def add_service(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('services_list')  # Перенаправление на страницу со списком услуг
    else:
        form = ServiceForm()
    return render(request, 'add_service.html', {'form': form})

# Редактировать услугу
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('services_list')  # Перенаправление на страницу со списком услуг
    else:
        form = ServiceForm(instance=service)
    return render(request, 'edit_service.html', {'form': form, 'service': service})

# Удалить услугу
def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        service.delete()
        return redirect('services_list')  # Перенаправление на страницу со списком услуг
    return render(request, 'delete_service.html', {'service': service})

# Список услуг
def services_list(request):
    services = Service.objects.all()
    return render(request, 'service_list.html', {'services': services})

# Список оборудования
def equipment_list(request):
    equipment_list = Equipment.objects.all()
    return render(request, 'equipment_list.html', {'equipment_list': equipment_list})

# Добавление оборудования
def add_equipment(request):
    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('equipment_list')
    else:
        form = EquipmentForm()
    return render(request, 'add_equipment.html', {'form': form})

# Редактирование оборудования
def edit_equipment(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            form.save()
            return redirect('equipment_list')
    else:
        form = EquipmentForm(instance=equipment)
    return render(request, 'edit_equipment.html', {'form': form, 'equipment': equipment})

# Удаление оборудования
def delete_equipment(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if request.method == 'POST':
        equipment.delete()
        return redirect('equipment_list')
    return render(request, 'delete_equipment.html', {'equipment': equipment})

# Просмотр инвентаря на день
def daily_inventory_list(request):
    inventories = DailyInventory.objects.all()
    return render(request, 'daily_inventory_list.html', {'inventories': inventories})

# Просмотр деталей инвентаря на день с использованием оборудования
def daily_inventory_detail(request, inventory_id):
    inventory = get_object_or_404(DailyInventory, id=inventory_id)
    equipment_usage = EquipmentUsage.objects.filter(daily_inventory=inventory)
    return render(request, 'daily_inventory_detail.html', {'inventory': inventory, 'equipment_usage': equipment_usage})

# Создание нового инвентаря на день
def daily_inventory_create(request):
    if request.method == 'POST':
        form = DailyInventoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('daily_inventory_list')
    else:
        form = DailyInventoryForm()
    return render(request, 'daily_inventory_form.html', {'form': form})

# Редактирование инвентаря на день
def daily_inventory_edit(request, inventory_id):
    inventory = get_object_or_404(DailyInventory, id=inventory_id)
    if request.method == 'POST':
        form = DailyInventoryForm(request.POST, instance=inventory)
        if form.is_valid():
            form.save()
            return redirect('daily_inventory_list')
    else:
        form = DailyInventoryForm(instance=inventory)
    return render(request, 'daily_inventory_form.html', {'form': form})

# Удаление инвентаря на день
def daily_inventory_delete(request, inventory_id):
    inventory = get_object_or_404(DailyInventory, id=inventory_id)
    inventory.delete()
    return redirect('daily_inventory_list')

# Создание записи использования оборудования
def equipment_usage_create(request, inventory_id):
    inventory = get_object_or_404(DailyInventory, id=inventory_id)
    if request.method == 'POST':
        form = EquipmentUsageForm(request.POST)
        if form.is_valid():
            equipment_usage = form.save(commit=False)
            equipment_usage.daily_inventory = inventory
            equipment_usage.save()
            return redirect('daily_inventory_detail', inventory_id=inventory.id)
    else:
        form = EquipmentUsageForm()
    return render(request, 'equipment_usage_form.html', {'form': form, 'inventory': inventory})

# Удаление записи использования оборудования
def equipment_usage_delete(request, usage_id):
    usage = get_object_or_404(EquipmentUsage, id=usage_id)
    inventory_id = usage.daily_inventory.id
    usage.delete()
    return redirect('daily_inventory_detail', inventory_id=inventory_id)

# Просмотр всех клиентов
def customer_list(request):
    customers = Customer.objects.all()
    return render(request, 'customer_list.html', {'customers': customers})

# Просмотр деталей клиента
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    return render(request, 'customer_detail.html', {'customer': customer})

# Создание нового клиента
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm()
    return render(request, 'customer_form.html', {'form': form})

# Редактирование клиента
def customer_edit(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'customer_form.html', {'form': form})

# Удаление клиента
def customer_delete(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    customer.delete()
    return redirect('customer_list')

def index(request):
    return render(request, 'index.html')