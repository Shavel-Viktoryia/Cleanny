from django.contrib import admin
from django.urls import path, include  # Правильный импорт include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),  # Подключаем маршруты приложения 'main'
]
