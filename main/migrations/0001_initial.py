# Generated by Django 5.1.3 on 2024-11-20 06:02

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('nickname', models.CharField(blank=True, max_length=50, null=True)),
                ('telegram_id', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('contact_number', models.CharField(max_length=20)),
                ('email', models.EmailField(max_length=254)),
            ],
        ),
        migrations.CreateModel(
            name='DailyInventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('status', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Equipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('type', models.CharField(choices=[('Многоразовое', 'многоразовое'), ('Одноразовое', 'одноразовое')], max_length=20)),
                ('quantity', models.IntegerField()),
                ('last_restocked', models.DateField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Personnel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_id', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('nickname', models.CharField(blank=True, max_length=50, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True)),
                ('email', models.EmailField(blank=True, default='notprovided@example.com', max_length=254, null=True)),
                ('hours_worked_today', models.DecimalField(decimal_places=2, default=0, max_digits=4)),
                ('hours_worked_week', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('last_order_end_time', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('duration_minutes', models.IntegerField()),
                ('is_quantity_modifiable', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Admin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('permissions', models.CharField(max_length=200)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_address', models.TextField()),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to='main.customer')),
            ],
        ),
        migrations.CreateModel(
            name='EquipmentUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_used', models.IntegerField()),
                ('returned_quantity', models.IntegerField(default=0)),
                ('daily_inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.dailyinventory')),
                ('equipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.equipment')),
            ],
        ),
        migrations.AddField(
            model_name='dailyinventory',
            name='equipment',
            field=models.ManyToManyField(through='main.EquipmentUsage', to='main.equipment'),
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled_time', models.DateTimeField()),
                ('status', models.CharField(choices=[('В ожидании', 'в ожидании'), ('В процессе', 'в процессе'), ('Завершено', 'завершено'), ('Отменено', 'отменено')], default='В ожидании', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('travel_time_minutes', models.IntegerField(default=30)),
                ('total_price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_duration_minutes', models.IntegerField(default=0)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.customer')),
                ('personnel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='main.personnel')),
                ('services', models.ManyToManyField(related_name='orders', to='main.service')),
            ],
        ),
        migrations.AddField(
            model_name='dailyinventory',
            name='personnel',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.personnel'),
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.IntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('comment', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.customer')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='main.order')),
            ],
        ),
        migrations.CreateModel(
            name='MonthlyStatistics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.DateField()),
                ('total_orders', models.IntegerField()),
                ('total_disposable_used', models.IntegerField()),
                ('total_reusable_used', models.IntegerField(default=0)),
                ('total_income', models.DecimalField(decimal_places=2, max_digits=10)),
                ('total_hours_worked', models.DecimalField(decimal_places=2, max_digits=5)),
                ('equipment_usage', models.ManyToManyField(blank=True, to='main.equipmentusage')),
                ('orders', models.ManyToManyField(blank=True, to='main.order')),
                ('personnel', models.ManyToManyField(blank=True, to='main.personnel')),
                ('services', models.ManyToManyField(blank=True, to='main.service')),
            ],
        ),
        migrations.CreateModel(
            name='WorkSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('schedule_url', models.URLField()),
                ('schedule_data', models.JSONField(blank=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('personnel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.personnel')),
            ],
        ),
        migrations.CreateModel(
            name='OrderService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_services', to='main.order')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.service')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('order', 'service'), name='unique_order_service')],
            },
        ),
    ]