from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('schedule/edit/<int:schedule_id>/', views.edit_schedule, name='edit_schedule'),
    path('schedule/new/', views.edit_schedule, name='new_schedule'),
    path('schedule/', views.schedule_list, name='schedule_list')
]
