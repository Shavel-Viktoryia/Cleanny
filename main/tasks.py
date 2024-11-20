from celery import shared_task
from django.utils import timezone
from .models import MonthlyStatistics, Order, EquipmentUsage
from django.db.models import Sum


@shared_task
def update_monthly_statistics():
    current_month = timezone.now().replace(day=1)
    statistics, created = MonthlyStatistics.objects.get_or_create(month=current_month)

    # Собираем данные как в предыдущем примере
    total_orders = Order.objects.filter(created_at__month=current_month.month).count()
    total_income = Order.objects.filter(created_at__month=current_month.month).aggregate(Sum('total_price'))[
                       'total_price__sum'] or 0
    total_hours_worked = sum(
        order.total_duration_minutes for order in Order.objects.filter(created_at__month=current_month.month))

    statistics.total_orders = total_orders
    statistics.total_income = total_income
    statistics.total_hours_worked = total_hours_worked

    total_disposable_used = EquipmentUsage.objects.filter(daily_inventory__date__month=current_month.month,
                                                          equipment__type='Одноразовое').aggregate(
        Sum('quantity_used'))['quantity_used__sum'] or 0
    total_reusable_used = EquipmentUsage.objects.filter(daily_inventory__date__month=current_month.month,
                                                        equipment__type='Многоразовое').aggregate(Sum('quantity_used'))[
                              'quantity_used__sum'] or 0

    statistics.total_disposable_used = total_disposable_used
    statistics.total_reusable_used = total_reusable_used

    statistics.save()
