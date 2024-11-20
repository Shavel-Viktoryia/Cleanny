from django.contrib import admin
from django.urls import path, include
from .views import work_schedule_view

urlpatterns = [
    path('schedule/', work_schedule_view, name='work_schedule_view')
]
