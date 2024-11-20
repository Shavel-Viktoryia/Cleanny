from django.contrib import admin
from .models import (Service, Customer, Review, Personnel, Order,
                     Equipment, DailyInventory, EquipmentUsage, WorkSchedule,
                     Admin, MonthlyStatistics, Address, OrderService)


# Register your models here.
admin.site.register(Service)
admin.site.register(Customer)
admin.site.register(Review)
admin.site.register(Personnel)
admin.site.register(Order)
admin.site.register(Equipment)
admin.site.register(DailyInventory)
admin.site.register(EquipmentUsage)
admin.site.register(WorkSchedule)
admin.site.register(Admin)
admin.site.register(MonthlyStatistics)
admin.site.register(Address)
admin.site.register(OrderService)