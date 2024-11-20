# myproject/celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Устанавливаем конфигурацию Django для Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cleaner.settings')

app = Celery('Cleaner')

# Используем строку конфигурации Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Загружаем задачи из всех зарегистрированных Django приложений
app.autodiscover_tasks()

# Настроим Celery Beat для регулярных задач
from celery.schedules import crontab

app.conf.beat_schedule = {
    'update-monthly-statistics-every-month': {
        'task': 'main.tasks.update_monthly_statistics',
        'schedule': crontab(minute=0, hour=0, day_of_month=1),  # Каждый 1-й день месяца в полночь
    },
}
