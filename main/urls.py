from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('schedule/edit/<int:schedule_id>/', views.edit_schedule, name='edit_schedule'),
    path('schedule/new/', views.edit_schedule, name='new_schedule'),
    path('schedule/', views.schedule_list, name='schedule_list'),
    path('personnel/', views.personnel_list, name='personnel_list'),
    path('personnel/edit/<int:pk>/', views.edit_personnel, name='edit_personnel'),
    path('order/', views.order_list, name='order_list'),  # Страница списка заказов
    path('order/create/', views.create_order, name='create_order'),  # Страница создания нового заказа
    path('order/edit/<int:order_id>/', views.edit_order, name='edit_order'),  # Страница редактирования заказа
    path('order/delete/<int:order_id>/', views.delete_order, name='delete_order'),  # Страница удаления заказа
    path('service/', views.services_list, name='services_list'),
    path('service/add/', views.add_service, name='add_service'),
    path('service/edit/<int:pk>/', views.edit_service, name='edit_service'),
    path('service/delete/<int:pk>/', views.delete_service, name='delete_service'),
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/add/', views.add_equipment, name='add_equipment'),
    path('equipment/edit/<int:pk>/', views.edit_equipment, name='edit_equipment'),
    path('equipment/delete/<int:pk>/', views.delete_equipment, name='delete_equipment'),
    path('inventory/', views.daily_inventory_list, name='daily_inventory_list'),
    path('inventory/<int:inventory_id>/', views.daily_inventory_detail, name='daily_inventory_detail'),
    path('inventory/create/', views.daily_inventory_create, name='daily_inventory_create'),
    path('inventory/<int:inventory_id>/edit/', views.daily_inventory_edit, name='daily_inventory_edit'),
    path('inventory/<int:inventory_id>/delete/', views.daily_inventory_delete, name='daily_inventory_delete'),
    path('inventory/<int:inventory_id>/equipment/create/', views.equipment_usage_create, name='equipment_usage_create'),
    path('equipment/<int:usage_id>/delete/', views.equipment_usage_delete, name='equipment_usage_delete'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customer/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customer/create/', views.customer_create, name='customer_create'),
    path('customer/<int:customer_id>/edit/', views.customer_edit, name='customer_edit'),
    path('customer/<int:customer_id>/delete/', views.customer_delete, name='customer_delete'),
]

