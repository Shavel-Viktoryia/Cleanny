from datetime import timedelta, datetime
from email.policy import default
from pickle import TUPLE
from tkinter.constants import CASCADE
from django.conf import settings

from django.contrib.admin.utils import build_q_object_from_lookup_parameters
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.utils.timezone import now

# Create your models here.
# Модель для услуг
class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField() # Длительность услуги в минутах
    is_quantity_modifiable = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# Модель для клиентов
class Customer(models.Model):
    name = models.CharField(max_length=100)
    nickname = models.CharField(max_length=50, blank=True, null=True)
    telegram_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    contact_number = models.CharField(max_length=20)
    # address = models.TextField()
    email = models.EmailField()

    def __str__(self):
        return self.name

# Модель для адресов
class Address(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    full_address = models.TextField()

    def __str__(self):
        return self.full_address

# Модель для отзывов
class Review(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Отзыв от {self.customer.name} на {self.order}'

# Модель для персонала
class Personnel(models.Model):
    telegram_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nickname = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)  # Добавлен default
    email = models.EmailField(default='notprovided@example.com', null=True, blank=True)
    hours_worked_today = models.DecimalField(max_digits=4, decimal_places=2, default=0)  # Часы работы в день
    hours_worked_week = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Часы работы за неделю
    last_order_end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nickname if self.nickname else f"User {self.telegram_id}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('В ожидании', 'в ожидании'),
        ('В процессе', 'в процессе'),
        ('Завершено', 'завершено'),
        ('Отменено', 'отменено')
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    services = models.ManyToManyField(Service, related_name='orders')
    personnel = models.ForeignKey(Personnel, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    scheduled_time = models.DateTimeField()  # Запланированное время начала уборки
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='В ожидании')
    created_at = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    travel_time_minutes = models.IntegerField(default=30)  # Время на дорогу
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_duration_minutes = models.IntegerField(default=0)  # Время выполнения услуг в минутах

    def __str__(self):
        # Получаем список названий услуг для этого заказа
        services_list = ', '.join([service.name for service in self.services.all()])
        return f'Заказ №{self.id} - {services_list} для {self.customer.name}'

    def remaining_time(self):
        """Метод для вычисления времени до запланированного начала"""
        now = timezone.now()  # Текущее время
        time_difference = self.scheduled_time - now
        return time_difference if time_difference > timedelta(0) else timedelta(0)

    def is_urgent(self):
        """Метод для проверки, является ли заказ срочным (например, если осталось менее 2 часов)"""
        return self.remaining_time() < timedelta(hours=2)

    def calculate_total_duration(self):
        """Метод для расчета общего времени выполнения услуг"""
        total_duration = 0
        for service in self.services.all():
            order_service = self.order_services.filter(service=service).first()
            if order_service:
                total_duration += service.duration_minutes * order_service.quantity
        self.total_duration_minutes = total_duration
        return total_duration

class OrderService(models.Model):
    order = models.ForeignKey(Order, related_name='order_services', on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)  # Количество заказанных услуг

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'service'], name='unique_order_service')
        ]

    def __str__(self):
        return f'{self.service.name} x{self.quantity} для {self.order.customer.name}'

# Модель для оборудования
class Equipment(models.Model):
    EQUIPMENT_TYPE_CHOICES = [
        ('Многоразовое', 'многоразовое'),
        ('Одноразовое', 'одноразовое')
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=EQUIPMENT_TYPE_CHOICES)
    quantity = models.IntegerField() # Количество единиц на складе
    last_restocked = models.DateField(null=True, blank=True) # Дата последнего пополнения

    def __str__(self):
        return self.name

# Модель для инвентаря на день
class DailyInventory(models.Model):
    date = models.DateField()
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE)
    equipment = models.ManyToManyField(Equipment, through='EquipmentUsage')
    status = models.BooleanField(default=False)

    def __str__(self):
        return f'Инвентарь на день для {self.personnel.nickname} на {self.date}'

# Модель для использования оборудования
class EquipmentUsage(models.Model):
    daily_inventory = models.ForeignKey(DailyInventory, on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    quantity_used = models.IntegerField() # Количество использованных единиц оборудования
    returned_quantity = models.IntegerField(default=0) # Количество возвращенного оборудования

    def __str__(self):
        return f'{self.quantity_used} {self.equipment.name} использовано {self.daily_inventory.personnel.nickname}'

# Модель для расписания работы (через Google таблицу)
class WorkSchedule(models.Model):
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE)
    schedule_url = models.URLField()  # Ссылка на Google Таблицу с расписанием
    schedule_data = models.JSONField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def fetch_schedule(self):
        """
        Получает расписание из таблицы с месяцем и днями недели, где работник отмечает + в день работы.
        """
        sheet_id = self.schedule_url.split('/')[5]  # Получаем ID из URL

        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_CREDENTIALS_FILE,
            scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)

        sheet = service.spreadsheets()
        try:
            result = sheet.values().get(spreadsheetId=sheet_id, range='A1:AF100').execute()
        except Exception as e:
            raise RuntimeError(f"Ошибка при доступе к Google Sheets: {e}")

        rows = result.get('values', [])
        if not rows or len(rows) < 3:
            raise ValueError("Некорректный формат таблицы")

        # Извлекаем месяц и год
        month_row = rows[0][1]  # Предполагается, что месяц в первой строке
        year = now().year
        try:
            month = datetime.strptime(month_row, '%B').month
        except ValueError:
            raise ValueError("Некорректное название месяца")

        header = rows[2]  # Третья строка содержит числа (1–31)
        schedule_data = []

        for row in rows[3:]:
            personnel_name = row[0]  # Имя сотрудника в первом столбце
            for i, day in enumerate(header[1:], start=1):  # Столбцы с днями
                if len(row) > i and row[i].strip() == '+':
                    schedule_data.append({
                        'personnel_name': personnel_name,
                        'date': f"{year}-{month:02d}-{int(day):02d}",
                        'hours': '8:00-17:00',
                        'comments': '',
                    })

        return schedule_data

    def update_schedule(self, data):
        """
        Обновляет расписание в Google Таблице.
        """
        sheet_id = self.schedule_url.split('/')[5]

        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_CREDENTIALS_FILE,
            scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)

        values = [[entry['personnel_name'], entry['date'], entry['hours'], entry['comments']] for entry in data]
        body = {'values': values}

        sheet = service.spreadsheets()
        try:
            sheet.values().update(
                spreadsheetId=sheet_id,
                range='A1:D{}'.format(len(values) + 1),
                valueInputOption='RAW',
                body=body
            ).execute()
        except Exception as e:
            raise RuntimeError(f"Ошибка при обновлении Google Sheets: {e}")

# Модель для администраторов
class Admin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    permissions = models.CharField(max_length=200) # Описание уровня доступа или ролей

    def __str__(self):
        return self.user.username

# Модель для статистики (заказы, траты оборудования и финансовая статистика)
class MonthlyStatistics(models.Model):
    month = models.DateField()
    total_orders = models.IntegerField()
    total_disposable_used = models.IntegerField() # Общие траты одноразового оборудования
    total_reusable_used = models.IntegerField(default=0) # Общие траты многоразового оборудования
    total_income = models.DecimalField(max_digits=10, decimal_places=2)
    total_hours_worked = models.DecimalField(max_digits=5, decimal_places=2)

    services = models.ManyToManyField(Service, blank=True)
    orders = models.ManyToManyField(Order, blank=True)
    personnel = models.ManyToManyField(Personnel, blank=True)
    equipment_usage = models.ManyToManyField(EquipmentUsage, blank=True)

    def __str__(self):
        return f'Статистика для {self.month.strftime("%B %Y")}'