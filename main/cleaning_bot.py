import os
import telegram
import asyncio
from calendar import calendar
from dataclasses import replace
from idlelib.editor import keynames
from re import fullmatch
from datetime import date
from telegram import Bot

import django
import sys

from django.conf.global_settings import DEFAULT_EXCEPTION_REPORTER
from django.core.files.locks import kernel32
from django.template.defaulttags import querystring
from django.db.models import QuerySet
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from pyexpat.errors import messages
from select import select
from datetime import datetime
from telegram import (Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton,
                      KeyboardButton, InputMediaPhoto)
from telegram.ext import (Updater, CommandHandler, MessageHandler, filters,
                          CallbackContext, Application, CallbackQueryHandler)
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
from asgiref.sync import sync_to_async
from datetime import timedelta
from django.utils import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from decimal import Decimal, ROUND_HALF_UP

# Добавление пути к Django проекту
sys.path.append('D:/Cleaner/Cleaner')

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleaning_bot.settings')
django.setup()

# Импорт моделей Django
from .models import (Customer, Address, Order, Service, OrderService, Personnel,
                     Equipment, EquipmentUsage, DailyInventory, Review)

# Токен Telegram бота
API_TOKEN = '8157684334:AAET35yD8IqRA5RIAal9JHhCDm210sX7zls'

# Состояния для ввода данных
NAME, CONTACT_NUMBER, EMAIL, ADD_ADDRESS, COMMENT = range(5)
STATE_COMMENT = "comment"

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния калькулятора
class CleaningCalculator:
    def __init__(self):
        self.rooms = 1
        self.bathrooms = 1
        self.total_price = Decimal('0.00')
        self.room_price = Decimal('0.00')
        self.bathrooms_price = Decimal('0.00')

    def update_price(self):
        """Обновляет стоимость на основе количества комнат и санузлов"""
        self.total_price = (self.room_price * self.rooms) + (self.bathrooms_price * self.bathrooms)
        return self.total_price

# Инициализация калькулятора
calculator = CleaningCalculator()

# Функция для проверки и создания пользователя
@sync_to_async
def check_or_create_user_sync(chat_id: str, username: str) -> None:
    user, created = Customer.objects.get_or_create(
        telegram_id=chat_id,
        defaults={
            "name": "Имя не указано",
            "contact_number": "Не указан",
            "email": "Не указан",
            "nickname": username
        }
    )

# Функция для получения информации о пользователе
@sync_to_async
def get_user_info(chat_id: str):
    user = Customer.objects.filter(telegram_id=chat_id).first()
    if user:
        return user.name, user.nickname, user.contact_number, user.email
    return None, None, None, None

# Функция для отображения адресов
async def show_addresses(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)

    # Получаем пользователя и его адреса
    customer = await sync_to_async(Customer.objects.filter(telegram_id=chat_id).first)()
    addresses = await sync_to_async(lambda: list(customer.addresses.all()))() if customer else []

    # Создаём inline-кнопки с адресами (не кликабельные)
    address_buttons = [
        [InlineKeyboardButton(address.full_address, callback_data=f"address_{address.id}")]
        for address in addresses
    ]

    # Добавляем кнопки "Добавить" и "Назад" как обычные клавиши
    reply_buttons = [
        ['Добавить', 'Назад']
    ]
    reply_markup = ReplyKeyboardMarkup(reply_buttons, one_time_keyboard=True)

    # Отображаем адреса и кнопки
    await update.message.reply_text("Ваши адреса:", reply_markup=InlineKeyboardMarkup(address_buttons))
    await update.message.reply_text("Выберите опцию:", reply_markup=reply_markup)

# Функция для отображения истории заказов
async def show_orders(update: Update, context: CallbackContext) -> None:
    # Проверяем, откуда пришел запрос (из сообщения или callback)
    chat_id = str(update.message.chat_id if update.message else update.callback_query.message.chat_id)

    # Получаем пользователя
    customer = await sync_to_async(Customer.objects.filter(telegram_id=chat_id).first)()

    if customer:
        # Получаем все заказы пользователя
        orders = await sync_to_async(lambda: list(customer.order_set.all()))()

        # Создаём inline-кнопки с заказами (не кликабельные)
        order_buttons = [
            [InlineKeyboardButton(f"Заказ {order.id}", callback_data=f"order_{order.id}")]
            for order in orders
        ]

        # Кнопка "Назад"
        reply_buttons = [
            [InlineKeyboardButton("Назад", callback_data="back_to_orders")]
        ]

        # Проверяем, откуда пришел запрос
        if update.message:
            # Отправка сообщения с кнопками, если запрос пришел из сообщения
            await update.message.reply_text("Ваша история заказов:", reply_markup=InlineKeyboardMarkup(order_buttons))
        elif update.callback_query:
            # Обработка callback_query, если запрос пришел из callback
            await update.callback_query.message.edit_text("Ваша история заказов:", reply_markup=InlineKeyboardMarkup(order_buttons))

    else:
        # Если пользователя не найдено
        await update.callback_query.message.edit_text("Ошибка: Пользователь не найден.")

async def show_order_info(update: Update, context: CallbackContext) -> None:
    # Получаем номер заказа из callback_data
    order_id = update.callback_query.data.split('_')[1]
    chat_id = str(update.callback_query.message.chat_id)

    # Получаем заказ по ID с предзагрузкой данных о работнике, если он есть
    order = await sync_to_async(Order.objects.prefetch_related('personnel').get)(id=order_id)

    # Формируем сообщение с информацией о заказе
    order_info_text = f"Информация о заказе №{order.id}:\n" \
                      f"Статус: {order.status}\n" \
                      f"Запланированное время: {order.scheduled_time}\n" \
                      f"Цена: {order.total_price} руб.\n" \
                      f"Длительность: {order.total_duration_minutes} минут\n"

    # Добавляем список услуг
    order_services = await sync_to_async(list)(order.services.all())
    order_info_text += "\nУслуги:\n"
    for service in order_services:
        order_info_text += f"- {service.name} (Цена: {service.price} руб, Длительность: {service.duration_minutes} мин.)\n"

    # Добавляем информацию о работнике, если он есть
    if order.personnel:
        order_info_text += f"\nРаботник: {order.personnel.nickname} "
        if order.personnel.phone_number:
            order_info_text += f"({order.personnel.phone_number})\n"
        else:
            order_info_text += "(Номер телефона не указан)\n"
        if order.personnel.last_order_end_time:
            order_info_text += f"Время завершения последнего заказа: {order.personnel.last_order_end_time}\n"
    else:
        order_info_text += "\nРаботник не назначен.\n"

    # Добавляем время выполнения, если оно завершено
    if order.end_time:
        order_info_text += f"Время завершения: {order.end_time}\n"
    else:
        order_info_text += "Заказ ещё не завершён.\n"

    # Формируем кнопки для оценки и жалобы
    inline_buttons = [
        [InlineKeyboardButton("Оценить", callback_data=f"rate_{order.id}")]
    ]

    # Кнопки для навигации
    navigation_buttons = [
        [InlineKeyboardButton("Назад", callback_data="back_to_orders")]
    ]

    # Отправляем информацию о заказе
    await update.callback_query.message.edit_text(
        order_info_text,
        reply_markup=InlineKeyboardMarkup(inline_buttons + navigation_buttons)
    )

    # Ожидаем подтверждения от пользователя
    await update.callback_query.answer()

# Обработчик нажатия на кнопки оценки
async def handle_rate_order(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data

    # Если нажатие на кнопку "Назад", возвращаем пользователя к истории заказов
    if data == "back_to_orders":
        return await show_orders(update, context)

    # Обработка нажатия на кнопку "Оценить"
    if data.startswith('rating_'):
        return await handle_rating(update, context)  # Вызов функции handle_rating

    # Обработка нажатия на кнопку "Оставить комментарий"
    if data.startswith("comment_"):
        return await handle_comment(update, context)

    # Проверка структуры данных
    split_data = data.split('_')
    if len(split_data) < 2:
        await query.answer("Неверный формат данных.", show_alert=True)
        return

    order_id = split_data[1]

    # Получение заказа из базы данных
    try:
        order = await sync_to_async(Order.objects.get)(id=order_id)
    except ObjectDoesNotExist:
        await query.answer("Заказ не найден.", show_alert=True)
        return

    # Проверка на завершенность заказа
    if order.status != 'Завершено':
        await query.answer("Оценить можно только завершённые заказы.", show_alert=True)
        return

    # Формирование кнопок для оценки
    rating_buttons = [
        [InlineKeyboardButton(str(i), callback_data=f"rating_{order_id}_{i}") for i in range(1, 6)],
        [InlineKeyboardButton("Оставить комментарий", callback_data=f"comment_{order_id}")],
        [InlineKeyboardButton("Назад", callback_data="back_to_orders")],
    ]

    new_text = "Спасибо, что выбрали нас! Оцените качество выполненной услуги."
    new_markup = InlineKeyboardMarkup(rating_buttons)

    # Проверяем, изменился ли текст, чтобы избежать лишнего редактирования
    if query.message.text != new_text:
        await query.message.edit_text(
            new_text,
            reply_markup=new_markup
        )

    await query.answer()  # Отправить уведомление, что запрос принят

# Обработчик для кнопки "Оценить"
async def handle_rating(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data

    # Извлекаем ID заказа и рейтинг из callback_data
    order_id, rating = data.split('_')[1], int(data.split('_')[2])

    # Получаем заказ из базы данных
    order = await sync_to_async(Order.objects.get)(id=order_id)

    # Получаем клиента
    chat_id = str(update.callback_query.message.chat_id)
    customer = await sync_to_async(Customer.objects.filter(telegram_id=chat_id).first)()

    # Проверяем, оставил ли уже этот пользователь оценку для данного заказа
    existing_review = await sync_to_async(Review.objects.filter(customer=customer, order=order).first)()

    if existing_review:
        # Если отзыв уже существует, показываем предупреждение
        await query.answer("Вы уже оставили оценку для этого заказа.", show_alert=True)
        return

    # Если отзыв не найден, сохраняем новый
    if customer:
        # Создаём новый отзыв
        review = Review(
            customer=customer,
            order=order,
            rating=rating,
            comment="Отзыв не указан"  # Можно дополнительно запросить комментарий, если необходимо
        )
        await sync_to_async(review.save)()

        # Ответ пользователю
        await query.answer("Спасибо за вашу оценку!")
        await query.message.edit_text("Ваша оценка успешно отправлена!")

        # Вы можете добавить здесь отправку уведомления для персонала или выполнить другие действия
    else:
        await query.answer("Ошибка: Пользователь не найден.", show_alert=True)

# Обработчик для кнопки "Оставить комментарий"
async def handle_comment(update: Update, context: CallbackContext) -> None:
    logger.info("handle_comment вызван.")
    query = update.callback_query
    data = query.data

    try:
        # Извлекаем ID заказа
        order_id = data.split('_')[1]
        context.user_data['current_order_id'] = order_id
        context.user_data['state'] = 'comment'
        logger.info(f"Установлен order_id: {order_id}. Состояние: 'comment'.")

        # Уведомляем пользователя
        await query.message.edit_text("Пожалуйста, оставьте ваш комментарий:")
        logger.info("Пользователю отправлено сообщение с запросом комментария.")
    except IndexError as e:
        logger.error(f"Ошибка извлечения ID заказа: {e}")
        await query.message.reply_text("Ошибка: неверный формат данных.")
    except Exception as e:
        logger.exception(f"Неожиданная ошибка: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте снова позже.")

# Обработчик для сохранения комментария
async def handle_comment_input(update: Update, context: CallbackContext) -> None:
    logger.info("handle_comment_input вызван.")
    state = context.user_data.get('state')
    logger.info(f"Текущее состояние: {state}")

    if state == 'comment':
        comment = update.message.text
        logger.info(f"Получен комментарий: {comment}")
        order_id = context.user_data.get('current_order_id')

        if not order_id:
            logger.warning("Не удалось определить заказ.")
            await update.message.reply_text("Ошибка: не удалось определить заказ.")
            return

        try:
            # Получаем заказ
            order = await sync_to_async(Order.objects.get)(id=order_id)
            logger.info(f"Заказ {order_id} успешно найден.")

            chat_id = str(update.message.chat_id)
            customer = await sync_to_async(Customer.objects.filter(telegram_id=chat_id).first)()

            if not customer:
                logger.warning("Клиент не найден.")
                await update.message.reply_text("Ошибка: пользователь не найден.")
                return

            # Создаём или обновляем отзыв
            review, created = await sync_to_async(Review.objects.get_or_create)(
                customer=customer,
                order=order,
                defaults={'rating': 0, 'comment': comment}
            )

            if not created:
                review.comment = comment
                await sync_to_async(review.save)()
                logger.info(f"Обновлён комментарий для заказа {order_id}: {comment}")
            else:
                logger.info(f"Добавлен новый комментарий для заказа {order_id}: {comment}")

            # Уведомляем пользователя
            await update.message.reply_text("Ваш комментарий успешно добавлен!")
            logger.info("Пользователю отправлено подтверждение.")

            # Сбрасываем состояние
            context.user_data['state'] = None
            context.user_data.pop('current_order_id', None)
        except Order.DoesNotExist:
            logger.error(f"Заказ {order_id} не найден.")
            await update.message.reply_text("Ошибка: заказ не найден.")
        except Exception as e:
            logger.exception(f"Ошибка при обработке комментария: {e}")
            await update.message.reply_text("Произошла ошибка. Попробуйте снова позже.")
    else:
        logger.info("Комментарий не ожидается в текущий момент.")
        await update.message.reply_text("Сейчас не ожидается комментарий.")

async def call_cleaning(update: Update, context: CallbackContext) -> None:
    # Проверяем, есть ли update.message или update.callback_query
    if update.message:
        chat_id = str(update.message.chat_id)
        message = update.message
    elif update.callback_query:  # Для callback query используем message из callback_query
        chat_id = str(update.callback_query.message.chat_id)
        message = update.callback_query.message
    else:
        # Если нет ни того, ни другого, выходим из функции
        return

    # Получаем пользователя и его адреса
    customer = await sync_to_async(Customer.objects.filter(telegram_id=chat_id).first)()
    addresses = await sync_to_async(lambda: list(customer.addresses.all()))() if customer else []

    # Если у пользователя нет адресов, показываем сообщение
    if not addresses:
        await message.reply_text("У вас нет сохранённых адресов. Пожалуйста, добавьте адрес.")
        return

    # Создаем inline кнопки
    address_buttons = [
        [InlineKeyboardButton(address.full_address, callback_data=f"address_cleaning_{address.id}")]
        for address in addresses
    ]

    # Обычные кнопки "Назад"
    reply_buttons = [
        ['Главное меню']
    ]

    # Отправляем сообщение с inline кнопками
    await message.reply_text(
        "Выберите адрес, где необходима уборка:",
        reply_markup=InlineKeyboardMarkup(address_buttons)
    )

    # Отправляем сообщение с обычной клавиатурой
    await message.reply_text(
        "Пожалуйста, выберите опцию:",
        reply_markup=ReplyKeyboardMarkup(reply_buttons, one_time_keyboard=True)
    )

    # Сохраняем выбранный адрес
    if update.callback_query:
        context.user_data['selected_address_to_cleaning'] = update.callback_query.data.split('_')[2]

async def show_calculator(update: Update, context: CallbackContext) -> None:
    try:
        address_id = int(update.callback_query.data.split('_')[2])
    except (IndexError, ValueError):
        await update.callback_query.answer("Неверный идентификатор адреса.")
        return

    address = await sync_to_async(Address.objects.get)(id=address_id)

    # Сохраняем выбранный адрес в context.user_data для дальнейшего использования
    context.user_data['selected_address'] = address

    # Получаем услуги для комнаты и санузла
    room_service = await sync_to_async(Service.objects.get)(name="Комната")
    bathroom_service = await sync_to_async(Service.objects.get)(name="Санузел")

    # Инициализируем стоимость для комнаты и санузла
    context.user_data['room_price'] = room_service.price
    context.user_data['bathrooms_price'] = bathroom_service.price

    # Если у пользователя ещё нет значений для комнат и санузлов, задаём начальные значения
    if 'rooms' not in context.user_data:
        context.user_data['rooms'] = 1  # Начальное количество комнат
    if 'bathrooms' not in context.user_data:
        context.user_data['bathrooms'] = 1  # Начальное количество санузлов

    # Инициализируем калькулятор с сохранёнными значениями
    context.user_data['rooms'] = context.user_data['rooms']
    context.user_data['bathrooms'] = context.user_data['bathrooms']

    # Обновляем общую стоимость
    total_price = (context.user_data['rooms'] * context.user_data['room_price']) + (context.user_data['bathrooms'] * context.user_data['bathrooms_price'])
    context.user_data['total_price'] = total_price

    # Создаем клавиатуру с кнопками
    keyboard = [
        [InlineKeyboardButton(f"Цена: {total_price} BYN", callback_data='price')],
        [
            InlineKeyboardButton('-', callback_data='decrease_rooms'),
            InlineKeyboardButton(f"Комнат: {context.user_data['rooms']}", callback_data='rooms'),
            InlineKeyboardButton('+', callback_data='increase_rooms'),
        ],
        [
            InlineKeyboardButton('-', callback_data='decrease_bathrooms'),
            InlineKeyboardButton(f"Санузлов: {context.user_data['bathrooms']}", callback_data='bathrooms'),
            InlineKeyboardButton('+', callback_data='increase_bathrooms'),
        ],
        [
            InlineKeyboardButton('Далее', callback_data='next'),
            InlineKeyboardButton('Назад', callback_data='back_to_call_cleaning')
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.edit_text(
        f"Вы выбрали адрес: {address.full_address}\n"
        "Используйте кнопки для изменения условий расчёта стоимости:",
        reply_markup=reply_markup
    )

# Функция для обновления данных пользователя
@sync_to_async
def update_user_info(chat_id: str, name: str = None, contact_number: str = None, email: str = None) -> None:
    user = Customer.objects.filter(telegram_id=chat_id).first()
    if user:
        if name:
            user.name = name
        if contact_number:
            user.contact_number = contact_number
        if email:
            user.email = email
        user.save()

# Основное меню
def main_menu() -> ReplyKeyboardMarkup:
    main_menu_buttons = [
        ['Профиль', 'О нас'],
        ['Вызов клининга', 'Техническая поддержка'],
        ['Список услуг']
    ]
    return ReplyKeyboardMarkup(main_menu_buttons, one_time_keyboard=True)

# Генерация инлайн-клавиатуры для списка услуг
def generate_services_keyboard(services):
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(service.name, callback_data=f'service_{service.id}')])
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд и сообщений
async def start(update: Update, context: CallbackContext) -> None:
    # Проверяем, откуда пришел запрос (из обычного сообщения или callback_query)
    if update.message:
        chat_id = str(update.message.chat_id)
        username = update.message.chat.username
    elif update.callback_query:
        chat_id = str(update.callback_query.from_user.id)
        username = update.callback_query.from_user.username
    else:
        # Если нет ни сообщения, ни callback_query, возвращаем ошибку
        return

    # Создаем или проверяем пользователя
    await check_or_create_user_sync(chat_id, username)

    welcome_text = "Добро пожаловать в CleannyBot! Я помогу вам с услугами по уборке. Выберите опцию ниже."

    # Changed to InlineKeyboardMarkup here
    reply_markup = main_menu()  # Ensure this returns InlineKeyboardMarkup

    context.user_data['previous_menu'] = 'main'

    # Если запрос пришел от callback_query, отвечаем через него
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.edit_text(welcome_text, reply_markup=reply_markup)
    else:
        # Если запрос пришел от обычного сообщения, отвечаем через update.message
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# Асинхронная версия получения услуг
@sync_to_async
def get_services_all():
    return list(Service.objects.all())

# Асинхронная версия получения услуги по id
@sync_to_async
def get_service_by_id_all(service_id):
    try:
        return Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        return None

# Функция для создания обычной клавиатуры с кнопкой "Назад"
def generate_back_button():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)

# Обработчик для кнопки "Назад"
async def handle_back(update: Update, context: CallbackContext) -> None:
    # Перенаправляем пользователя в обработчик /start
    await start(update, context)

# Отображение списка услуг
async def show_services(update: Update, context: CallbackContext) -> None:
    services = await get_services_all()

    if services:
        # Генерируем инлайн-клавиатуру для услуг
        reply_markup_inline = generate_services_keyboard(services)
        text = "Вот список доступных услуг.\n" \
               "---------------------------------------------------------------------------\n\n" \
               "Нажмите на интересующую вас услугу для получения дополнительной информации:"
    else:
        reply_markup_inline = None
        text = "В данный момент услуг нет в списке."

    # Генерируем обычную клавиатуру с кнопкой "Назад"
    reply_markup_back = generate_back_button()

    # Проверяем, вызвана ли функция из callback-запроса
    if update.callback_query:
        query = update.callback_query
        await query.answer()  # Обязательно ответить на callback

        # Убираем inline-клавиатуру, затем показываем сообщение с обычной клавиатурой
        if reply_markup_inline:
            await query.message.edit_text(text, reply_markup=reply_markup_inline)
        else:
            await query.message.edit_text(text)
        await query.message.reply_text(
            "Нажмите 'Назад', чтобы вернуться в главное меню.",
            reply_markup=reply_markup_back,
        )
    else:
        # Если вызов из обычного сообщения, показываем текст с обеими клавиатурами
        await update.message.reply_text(text, reply_markup=reply_markup_inline)
        await update.message.reply_text(
            "Нажмите 'Назад', чтобы вернуться в главное меню.",
            reply_markup=reply_markup_back,
        )

# Обновляем обработчики
async def service_info(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()  # Обязательно ответить на callback

    # Извлекаем ID услуги из callback_data
    service_id = query.data.split('_')[1]

    # Получаем данные об услуге из базы
    service = await get_service_by_id_all(service_id)

    if service:
        # Формируем текст сообщения с информацией об услуге
        text = (
            f"Название услуги: {service.name}\n"
            f"Описание: {service.description}\n"
            f"Цена: {service.price} руб.\n"
            f"Длительность: {service.duration_minutes} минут\n"
            f"Изменяемое количество: {'Да' if service.is_quantity_modifiable else 'Нет'}"
        )

        # Создаём кнопку "Назад"
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад", callback_data="back_to_services")]
        ])
    else:
        text = "Услуга не найдена. Возможно, она была удалена."
        reply_markup = None

    # Отправляем сообщение пользователю
    await query.message.edit_text(text, reply_markup=reply_markup)

# Обработчик для кнопки "Назад" в service_info
async def back_to_services(update: Update, context: CallbackContext) -> None:
    await show_services(update, context)

# Обработчик для "О нас"
async def handle_about_us(update: Update, context: CallbackContext):
    # Текст для сообщения
    about_text = (
        "Занимайтесь любимыми делами,\n"
        "а уборку мы берём на себя!\n\n"
        "КлинниБогини –\n"
        "не просто клининговая компания.\n\n"
        "Мы создали удобный сервис\n"
        "для активных и счастливых людей."
    )

    # Картинка
    media_url = "https://avatars.mds.yandex.net/i?id=b61c492dcc6122063faa3f5d3d5c7ea9_l-6377202-images-thumbs&n=13"

    # Кнопка "Назад"
    back_button = InlineKeyboardButton("Назад", callback_data='back_after_about_us')

    # Формируем клавиатуру с кнопкой "Назад"
    keyboard = InlineKeyboardMarkup([[back_button]])

    # Отправляем сообщение с текстом и картинкой
    await update.message.reply_photo(
        photo=media_url,
        caption=about_text,  # Текст, который будет отправлен вместе с картинкой
        reply_markup=keyboard  # Добавляем клавиатуру
    )

# Обработчик для "Техническая поддержка"
async def handle_technical_support(update: Update, context: CallbackContext):
    # Текст для сообщения
    support_text = (
        "Если у вас возникли проблемы или вопросы,\n"
        "не стесняйтесь обращаться в нашу техническую поддержку!\n\n"
        "Мы всегда готовы помочь вам быстро и эффективно.\n\n"
        "Наш номер телефона:\n"
        "*+375 (44) 711-11-85*\n\n"
        "Ждём вашего обращения!"
    )

    # Картинка для техподдержки
    support_image_url = "https://avatars.mds.yandex.net/i?id=d112337a41e5d7d7b5f353578f3c2469_l-6311181-images-thumbs&n=13"  # Замените на нужную ссылку на изображение

    # Кнопка "Назад"
    back_button = InlineKeyboardButton("Назад", callback_data='back_after_about_us')

    # Формируем клавиатуру с кнопкой "Назад"
    keyboard = InlineKeyboardMarkup([[back_button]])

    # Отправляем сообщение с текстом, картинкой и клавиатурой
    await update.message.reply_photo(
        photo=support_image_url,
        caption=support_text,  # Текст с номером и инструкциями
        reply_markup=keyboard  # Добавляем клавиатуру с кнопкой "Назад"
    )

# Обработчик для кнопки "Назад" в разделе "О нас"
async def handle_back_after_about_us(update: Update, context: CallbackContext) -> None:
    # Удаляем сообщение с изображением и клавиатурой, если это callback_query
    if update.callback_query:
        await update.callback_query.message.delete()
        await start(update.callback_query, context)

# Функция отображения профиля
async def profile(update: Update, context: CallbackContext) -> None:
    # Проверяем, пришёл ли запрос через обычное сообщение или callback_query
    if update.message:
        chat_id = str(update.message.chat_id)
        send_message = update.message.reply_text
    elif update.callback_query:
        chat_id = str(update.callback_query.message.chat_id)
        send_message = update.callback_query.message.reply_text
    else:
        # Если нет ни одного, выводим сообщение об ошибке и выходим
        await update.callback_query.message.reply_text("Ошибка: не удалось получить ID чата.")
        return

    # Получаем информацию о пользователе
    name, nickname, contact_number, email = await get_user_info(chat_id)

    if not name:
        await send_message("Ваш профиль не найден. Попробуйте снова.")
        return

    profile_text = (
        f"Профиль:\n"
        f"Имя: {name}\n"
        f"Ник: {nickname}\n"
        f"Контактный номер: {contact_number}\n"
        f"Email: {email}"
    )

    profile_menu = [
        ['Сменить все контактные данные'],
        ['Адреса', 'История заказов'],
        ['Главное меню']
    ]
    reply_markup = ReplyKeyboardMarkup(profile_menu, one_time_keyboard=True)
    context.user_data['previous_menu'] = 'profile'

    # Используем send_message для отправки ответа в зависимости от источника вызова
    await send_message(profile_text, reply_markup=reply_markup)

# Обработчик для профиля
async def handle_profile_action(update: Update, context: CallbackContext) -> None:
    text = update.message.text

    if text == "Сменить все контактные данные":
        await update.message.reply_text("Введите ваше новое имя:")
        context.user_data["state"] = NAME
    elif text == "Адреса":
        context.user_data['previous_menu'] = 'profile'
        await show_addresses(update, context)
    elif text == "История заказов":
        context.user_data['previous_menu'] = 'profile'
        await show_orders(update, context)
    elif text == "Главное меню":
        await start(update, context)

# Обработчик ввода новых данных
async def handle_new_data(update: Update, context: CallbackContext) -> None:
    user_state = context.user_data.get("state")

    if user_state == NAME:
        await handle_new_name(update, context)
    elif user_state == CONTACT_NUMBER:
        await handle_new_contact_number(update, context)
    elif user_state == EMAIL:
        await handle_new_email(update, context)
    elif user_state == ADD_ADDRESS:
        await handle_new_address(update, context)

async def handle_new_name(update: Update, context: CallbackContext) -> None:
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Введите ваш новый контактный номер:")
    context.user_data["state"] = CONTACT_NUMBER

async def handle_new_contact_number(update: Update, context: CallbackContext) -> None:
    context.user_data["contact_number"] = update.message.text
    await update.message.reply_text("Введите ваш новый email:")
    context.user_data["state"] = EMAIL

async def handle_new_email(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)
    email = update.message.text
    name = context.user_data.get("name")
    contact_number = context.user_data.get("contact_number")

    await update_user_info(chat_id, name=name, contact_number=contact_number, email=email)
    await update.message.reply_text("Ваши данные успешно обновлены!")
    context.user_data.clear()
    await profile(update, context)

# Обработчик для действий с адресами
async def handle_address_action(update: Update, context: CallbackContext) -> None:
    text = update.message.text

    if text == "Добавить":
        await update.message.reply_text("Введите ваш новый адрес:")
        context.user_data["state"] = ADD_ADDRESS
    elif text == "Назад":
        await profile(update, context)

# Обработчик для истории заказов
async def handle_orders_action(update: Update, context: CallbackContext) -> None:
    text = update.message.text

    if text == 'Назад':
        await profile(update, context)

# Обработчик ввода нового адреса
async def handle_new_address(update: Update, context: CallbackContext) -> None:
    new_address = update.message.text
    chat_id = str(update.message.chat_id)
    address_id = context.user_data.get("editing_address_id")

    if address_id:
        # Обновление адреса
        await sync_to_async(Address.objects.filter(id=address_id).update)(full_address=new_address)
        await update.message.reply_text("Адрес успешно изменен!")
        context.user_data.pop("editing_address_id")
    else:
        # Создание нового адреса
        customer = await sync_to_async(Customer.objects.filter(telegram_id=chat_id).first)()
        if customer:
            await sync_to_async(Address.objects.create)(customer=customer, full_address=new_address)
            await update.message.reply_text("Адрес успешно добавлен!")

    await show_addresses(update, context)

# Обработчик для выбора действий с адресом
async def handle_address_choice(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    address_id = query.data.split("_")[1]

    # Показываем кнопки "Удалить" и "Изменить"
    action_buttons = [
        [InlineKeyboardButton("Изменить", callback_data=f"edit_{address_id}")],
        [InlineKeyboardButton("Удалить", callback_data=f"delete_{address_id}")]
    ]
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(action_buttons))

async def handle_calculator(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    action = query.data

    # Получаем выбранный адрес из context.user_data
    address = context.user_data.get('selected_address')

    # Инициализация значений по умолчанию, если их нет
    if 'rooms' not in context.user_data:
        context.user_data['rooms'] = 1  # Значение по умолчанию
    if 'bathrooms' not in context.user_data:
        context.user_data['bathrooms'] = 1  # Значение по умолчанию

    # Обрабатываем изменение количества комнат
    if action == 'decrease_rooms':
        context.user_data['rooms'] = max(1, context.user_data['rooms'] - 1)
    elif action == 'increase_rooms':
        context.user_data['rooms'] += 1

    # Обрабатываем изменение количества санузлов
    elif action == 'decrease_bathrooms':
        context.user_data['bathrooms'] = max(1, context.user_data['bathrooms'] - 1)
    elif action == 'increase_bathrooms':
        context.user_data['bathrooms'] += 1

    # Переход к следующему шагу
    elif action == 'next':
        await handle_next_step(update, context)
        return
    elif action == 'back_to_call_cleaning':
        await call_cleaning(update, context)
        return

    # Пересчитываем общую стоимость
    total_price = (context.user_data['rooms'] * context.user_data['room_price']) + (context.user_data['bathrooms'] * context.user_data['bathrooms_price'])
    context.user_data['total_price'] = total_price

    # Обновляем клавиатуру с новыми данными
    keyboard = [
        [InlineKeyboardButton(f"Цена: {total_price} BYN", callback_data='price')],
        [
            InlineKeyboardButton('-', callback_data='decrease_rooms'),
            InlineKeyboardButton(f"Комнат: {context.user_data['rooms']}", callback_data='rooms'),
            InlineKeyboardButton('+', callback_data='increase_rooms'),
        ],
        [
            InlineKeyboardButton('-', callback_data='decrease_bathrooms'),
            InlineKeyboardButton(f"Санузлов: {context.user_data['bathrooms']}", callback_data='bathrooms'),
            InlineKeyboardButton('+', callback_data='increase_bathrooms'),
        ],
        [
            InlineKeyboardButton('Далее', callback_data='next'),
            InlineKeyboardButton('Назад', callback_data='back_to_call_cleaning')
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Обновляем текст и клавиатуру
    await query.message.edit_text(
        f"Вы выбрали адрес: {address.full_address}\n"
        "Используйте кнопки для изменения условий расчёта стоимости:",
        reply_markup=reply_markup
    )

# Обработчик для кнопки "Далее"
async def handle_next_step(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    chat_id = str(query.message.chat_id)

    # Получаем данные пользователя из context.user_data
    name, nickname, contact_number, email = await get_user_info(chat_id)
    address = context.user_data.get('selected_address')
    rooms = context.user_data.get('rooms', 1)  # Если не указано, по умолчанию 1
    bathrooms = context.user_data.get('bathrooms', 1)  # Если не указано, по умолчанию 1
    total_price = context.user_data.get('total_price', 0)  # Получаем общую цену, если есть

    # Формируем сообщение с данными пользователя
    user_data_text = (
        f"Ваши данные:\n"
        f"Имя: {name}\n"
        f"Ник: {nickname}\n"
        f"Контактный номер: {contact_number}\n"
        f"Email: {email}\n"
        f"Адрес уборки: {address.full_address if address else 'Не указан'}\n"
        f"Количество комнат: {rooms}\n"
        f"Количество санузлов: {bathrooms}\n"
        f"Общая стоимость: {total_price} BYN\n\n"
        "Ваши данные соответствуют введённым при регистрации?"
    )

    # Inline-клавиатура с кнопками "Да" и "Нет"
    keyboard = [
        [
            InlineKeyboardButton("Да", callback_data='confirm_data_yes'),
            InlineKeyboardButton("Нет", callback_data='confirm_data_no')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с данными и кнопками
    await query.message.reply_text(user_data_text, reply_markup=reply_markup)

# Обработчик для подтверждения "Да"
async def confirm_data_yes(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id

    # Создаем календарь для выбора даты
    calendar, step = DetailedTelegramCalendar().build()

    # Отправляем сообщение с календарем
    await query.message.reply_text(
        f"Выберите {LSTEP[step]} для заказа клининга:",
        reply_markup=calendar
    )

# Обработчик для выбора даты
async def calendar_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not hasattr(query, 'data'):
        return  # Завершаем, если нет данных в query

    print(f"Callback data: {query.data}")

    try:
        result, key, step = DetailedTelegramCalendar().process(query.data)
    except KeyError as e:
        print(f"KeyError: {e}. Callback data might be malformed: {query.data}")
        return

    if not result and key:
        await query.edit_message_text(
            f"Выберите {LSTEP[step]} для заказа клининга:",
            reply_markup=key
        )
    elif result:
        # Проверяем, что выбранная дата не раньше сегодняшнего дня
        today = datetime.now().date()
        if result < today:
            await query.answer("Дата должна быть сегодня или позже!", show_alert=True)
            return

        # Если дата валидна, сохраняем её и переходим к выбору времени
        selected_date = result.strftime('%d-%m-%Y')  # Форматируем как строку
        context.user_data['selected_date'] = selected_date

        await query.edit_message_text(f"Вы выбрали дату: {selected_date}. Теперь выберите время.")

        # Переходим к выбору времени
        await send_time_selection(query, selected_date)

# Функция для отправки кнопок с выбором времени
async def send_time_selection(query, selected_date):
    # Создаем inline-клавиатуру с выбором времени с 9:00 до 18:00 с шагом в 30 минут
    time_buttons = []
    for hour in range(9, 19):  # 9:00 - 18:00 (до 18:00, не включая 18:30)
        for minute in ['00', '30']:
            if hour == 18 and minute == '30':
                continue  # Пропускаем 18:30
            time_buttons.append(InlineKeyboardButton(f"{hour}:{minute}", callback_data=f"time_{hour}:{minute}"))

    # Переупорядочиваем кнопки в строки по 3 кнопки в каждой
    compact_buttons = [time_buttons[i:i+3] for i in range(0, len(time_buttons), 3)]

    # Генерируем клавиатуру
    keyboard = InlineKeyboardMarkup(compact_buttons)

    # Отправляем пользователю кнопки с выбором времени
    await query.message.reply_text(
        f"Вы выбрали {selected_date}. Теперь выберите время для клининга:",
        reply_markup=keyboard
    )

# Обработчик для выбора времени
async def time_selection_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not hasattr(query, 'data'):
        return  # Завершаем, если нет данных в query

    time = query.data.split('_')[1]  # Получаем время (например, "15:00")

    # Сохраняем выбранное время в контексте
    context.user_data['selected_time'] = time

    # Подтверждаем выбор времени
    await query.edit_message_text(f"Вы выбрали время: {time}")

    # Переход к следующему шагу
    await handle_next_step_after_choosing_date(update, context)

async def handle_next_step_after_choosing_date(update: Update, context: CallbackContext):
    selected_date = context.user_data.get('selected_date')
    selected_time = context.user_data.get('selected_time')

    # Проверка наличия выбранной даты и времени
    if selected_date and selected_time:
        # Преобразование выбранной даты и времени в объект datetime
        try:
            selected_datetime_str = f"{selected_date} {selected_time}"
            selected_datetime = datetime.strptime(selected_datetime_str, '%d-%m-%Y %H:%M')

            # Сохраняем datetime в context.user_data
            context.user_data['scheduled_time'] = selected_datetime

            confirmation_message = f"Вы выбрали дату: {selected_date} и время {selected_time}.\n"
            confirmation_message += "Если вам необходимы дополнительные услуги, пожалуйста, выберите их ниже."
        except ValueError:
            confirmation_message = "Ошибка при преобразовании даты или времени. Пожалуйста, попробуйте снова."
    else:
        confirmation_message = "Не удалось получить информацию о выбранной дате или времени."

    # Отправляем сообщение с подтверждением выбора даты и времени
    try:
        keyboard = await create_service_keyboard(update, context)
    except Exception as e:
        print(f"Ошибка при создании клавиатуры: {e}")
        keyboard = None

    await update.callback_query.message.edit_text(
        confirmation_message,
        reply_markup=keyboard
    )

    # Переход к следующему шагу при нажатии на кнопку "Далее"
    if update.callback_query.data == 'next_step':
        # Если данные выбраны, переходим к выбору скидки
        await handle_choosing_discount(update, context)

@sync_to_async
def get_services():
    return list(Service.objects.exclude(name__in=["Комната", "Санузел"]))

@sync_to_async
def get_service_by_id(service_id):
    return Service.objects.get(id=service_id)

async def create_service_keyboard(update, context):
    services = await get_services()  # Получаем все услуги
    total_price = context.user_data.get('total_price', Decimal('0.00'))
    selected_services = context.user_data.get('selected_services', {})

    keyboard = [
        [InlineKeyboardButton(f"Итоговая цена: {total_price} BYN", callback_data='total_price')]
    ]

    for service in services:
        if service.id in selected_services:
            quantity = selected_services[service.id]
            if service.is_quantity_modifiable:
                # Кнопки для изменения количества (минус, плюс)
                keyboard.append([
                    InlineKeyboardButton(f"{service.name} ({quantity})", callback_data=f"service_{service.id}_info"),
                    InlineKeyboardButton("-", callback_data=f"service_{service.id}_remove"),
                    InlineKeyboardButton("+", callback_data=f"service_{service.id}_add"),
                    InlineKeyboardButton(f"{service.price * quantity} BYN", callback_data=f"service_{service.id}_price")
                ])
            else:
                # Услуга без возможности изменения количества
                keyboard.append([
                    InlineKeyboardButton(f"{service.name} (выбрано)", callback_data=f"service_{service.id}_selected"),
                    InlineKeyboardButton(f"{service.price} BYN", callback_data=f"service_{service.id}_price")
                ])
        else:
            if service.is_quantity_modifiable:
                # Услуга, которую можно добавить
                keyboard.append([
                    InlineKeyboardButton(f"{service.name} (выберите)", callback_data=f"service_{service.id}_add"),
                    InlineKeyboardButton(f"{service.price} BYN", callback_data=f"service_{service.id}_price")
                ])
            else:
                # Услуга, которую нельзя изменить
                keyboard.append([
                    InlineKeyboardButton(f"{service.name}", callback_data=f"service_{service.id}_select"),
                    InlineKeyboardButton(f"{service.price} BYN", callback_data=f"service_{service.id}_price")
                ])

    keyboard.append([InlineKeyboardButton('Далее', callback_data='next_step')])
    return InlineKeyboardMarkup(keyboard)

async def handle_service_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    action = query.data

    if action.startswith("service_"):
        parts = action.split("_")
        service_id = int(parts[1])
        action_type = parts[2]

        service = await get_service_by_id(service_id)
        selected_services = context.user_data.get('selected_services', {})
        total_price = context.user_data.get('total_price', Decimal('0.00'))
        click_count = context.user_data.get('click_count', {})  # Добавляем переменную для отслеживания количества нажатий

        if service.is_quantity_modifiable:
            if action_type == 'add':
                # Увеличиваем количество услуги
                selected_services[service_id] = selected_services.get(service_id, 0) + 1
                total_price += service.price  # добавляем цену добавляемой единицы услуги

            elif action_type == 'remove':
                # Уменьшаем количество услуги
                if service_id in selected_services:
                    if selected_services[service_id] > 1:
                        selected_services[service_id] -= 1
                        total_price -= service.price  # вычитаем цену удаляемой единицы услуги
                    else:
                        del selected_services[service_id]
                        total_price -= service.price  # вычитаем цену услуги, если её количество стало нулевым
        else:
            # Услуга с is_quantity_modifiable=False, отслеживаем чётность нажатий
            current_clicks = click_count.get(service_id, 0)
            if current_clicks % 2 == 0:
                # Чётное нажатие: добавляем услугу с количеством 1
                selected_services[service_id] = 1  # Добавляем услугу с количеством 1
                total_price += service.price  # Добавляем стоимость услуги
                await query.answer(f"Услуга '{service.name}' добавлена.")  # Уведомление о добавлении услуги
            else:
                # Нечётное нажатие: удаляем услугу
                if service_id in selected_services:
                    del selected_services[service_id]  # Убираем услугу из выбранных
                    total_price -= service.price  # Вычитаем стоимость услуги
                    await query.answer(f"Услуга '{service.name}' отменена.")  # Уведомление о отмене услуги

            # Обновляем счётчик нажатий для услуги
            click_count[service_id] = current_clicks + 1

        # Сохраняем выбранные услуги, итоговую цену и количество нажатий
        context.user_data['selected_services'] = selected_services
        context.user_data['total_price'] = total_price
        context.user_data['click_count'] = click_count  # Обновляем данные о нажатиях

        # Генерация клавиатуры
        keyboard = await create_service_keyboard(update, context)

        # Подготовка обновленного текста
        new_text = f"Итоговая цена: {total_price} BYN.\nВыберите дополнительные услуги или нажмите 'Далее'."

        # Проверка на изменения в тексте или клавиатуре
        if query.message.text != new_text or query.message.reply_markup != keyboard:
            await query.edit_message_text(new_text, reply_markup=keyboard)
        else:
            # Если изменений не произошло, выводим другое уведомление
            await query.answer("Никаких изменений не произошло.")  # Если изменений не произошло

async def handle_choosing_discount(update: Update, context: CallbackContext):
    # Сообщение с вопросом о частоте уборки
    message_text = "Как часто вам необходима уборка?"

    frequency_keyboard = [
        [
            InlineKeyboardButton("Раз в неделю", callback_data='frequency_weekly'),
            InlineKeyboardButton("15%", callback_data="discount_weekly")
        ],
        [
            InlineKeyboardButton("Раз в две недели", callback_data='frequency_biweekly'),
            InlineKeyboardButton("10%", callback_data="discount_biweekly")
        ],
        [
            InlineKeyboardButton("Раз в месяц", callback_data='frequency_monthly'),
            InlineKeyboardButton("7%", callback_data="discount_monthly")
        ],
        [
            InlineKeyboardButton("1 раз или первый раз", callback_data='frequency_once'),
            InlineKeyboardButton("0%", callback_data="discount_once")
        ]
    ]

    keyboard = InlineKeyboardMarkup(frequency_keyboard)

    await update.callback_query.message.edit_text(
        message_text,
        reply_markup=keyboard
    )

async def handle_frequency_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    frequency = query.data.split('_')[1]  # Тип частоты уборки, например, weekly

    # Обновляем выбранную частоту и скидку
    context.user_data['selected_frequency'] = frequency
    discount_values = {'weekly': Decimal('0.15'), 'biweekly': Decimal('0.10'), 'monthly': Decimal('0.07'), 'once': Decimal('0')}
    discount_percentage = discount_values.get(frequency, Decimal('0'))

    # Получаем стоимость и услуги
    room_price = context.user_data.get('room_price', Decimal('10.00'))
    bathroom_price = context.user_data.get('bathrooms_price', Decimal('5.00'))
    rooms = context.user_data.get('rooms', 1)
    bathrooms = context.user_data.get('bathrooms', 1)
    total_price = (rooms * room_price) + (bathrooms * bathroom_price)

    # Получаем выбранные дополнительные услуги
    selected_services = context.user_data.get('selected_services', {})
    for service_id, quantity in selected_services.items():
        service = await get_service_by_id(service_id)
        total_price += service.price * quantity

    # Рассчитываем итоговую цену с учетом скидки
    final_price = total_price * (Decimal('1') - discount_percentage)
    final_price = final_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Формируем итоговое сообщение
    user_data_text = (
        f"Количество комнат: {rooms}\n"
        f"Количество санузлов: {bathrooms}\n"
        f"Частота уборки: {frequency}\n"
        f"Скидка: {int(discount_percentage * 100)}%\n"
        f"Финальная цена: {final_price} BYN\n"
        "Подтвердите заказ или отмените."
    )

    # Отправляем сообщение с обновленными данными
    keyboard = [
        [
            InlineKeyboardButton("Отменить", callback_data='cancel_order'),
            InlineKeyboardButton("Оформить", callback_data='confirm_order')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(user_data_text, reply_markup=reply_markup)

@sync_to_async
def get_customer_by_chat_id(chat_id: str):
    try:
        return Customer.objects.get(telegram_id=chat_id)
    except Customer.DoesNotExist:
        return None

@sync_to_async
def create_order(customer, selected_services, personnel, scheduled_time, final_price, rooms, bathrooms):
    try:
        # Проверка на наличие значения для scheduled_time
        if not scheduled_time:
            raise ValueError("Scheduled time is required")

        # Начинаем транзакцию для обеспечения целостности данных
        with transaction.atomic():
            # Создание объекта заказа
            order = Order.objects.create(
                customer=customer,
                personnel=personnel,
                scheduled_time=scheduled_time,
                status='В ожидании',
                total_price=final_price
            )

            # Получаем все необходимые услуги в одном запросе
            service_ids = list(selected_services.keys())
            services = Service.objects.filter(id__in=service_ids)

            # Добавляем услуги в ManyToMany поле
            order.services.set(services)

            # Создаём записи в OrderService
            order_services = []
            for service in services:
                if service.duration_minutes is None:
                    service.duration_minutes = 30  # Значение по умолчанию
                order_services.append(OrderService(
                    order=order,
                    service=service,
                    quantity=selected_services.get(service.id, 1)
                ))

            # Добавляем услугу "Комнаты", если комнаты есть
            if rooms > 0:
                room_service = Service.objects.get(name="Комната")
                order_services.append(OrderService(order=order, service=room_service, quantity=rooms))
                order.services.add(room_service)

            # Добавляем услугу "Санузлы", если санузлы есть
            if bathrooms > 0:
                bathroom_service = Service.objects.get(name="Санузел")
                order_services.append(OrderService(order=order, service=bathroom_service, quantity=bathrooms))
                order.services.add(bathroom_service)

            # Сохраняем все записи OrderService
            OrderService.objects.bulk_create(order_services)

            # Рассчитываем общее время выполнения услуг
            order.calculate_total_duration()
            order.save()

        return order

    except IntegrityError as e:
        print(f"Ошибка базы данных при создании заказа: {e}")
        return None
    except Exception as e:
        print(f"Ошибка при создании заказа: {e}")
        return None

async def handle_confirm_order(update: Update, context: CallbackContext):
    query = update.callback_query

    rooms = context.user_data.get('rooms', 1)
    bathrooms = context.user_data.get('bathrooms', 1)
    total_price = context.user_data.get('total_price', Decimal('0.00'))

    frequency = context.user_data.get('selected_frequency', 'once')
    discount_values = {'weekly': Decimal('0.15'), 'biweekly': Decimal('0.10'), 'monthly': Decimal('0.07'),
                       'once': Decimal('0')}

    discount_percentage = discount_values.get(frequency, Decimal('0'))
    final_price = total_price * (Decimal('1') - discount_percentage)
    final_price = final_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    selected_services = context.user_data.get('selected_services', {})
    services_text = ""
    for service_id, quantity in selected_services.items():
        service = await get_service_by_id(service_id)
        services_text += f"{service.name} - {quantity} шт. по {service.price} BYN каждая. Итого: {service.price * quantity} BYN\n"

    if rooms > 0:
        services_text += f"Комнаты: {rooms} шт.\n"
    if bathrooms > 0:
        services_text += f"Санузлы: {bathrooms} шт.\n"

    customer = await get_customer_by_chat_id(query.from_user.id)
    if not customer:
        await query.message.edit_text("Не удалось найти пользователя в системе. Пожалуйста, попробуйте снова.")
        return

    scheduled_time = context.user_data.get('scheduled_time')
    if not scheduled_time:
        await query.message.edit_text("Не указано время для выполнения заказа. Пожалуйста, выберите время.")
        return

    personnel = None

    order = await create_order(customer, selected_services, personnel, scheduled_time, final_price, rooms, bathrooms)

    if order is None:
        await query.message.edit_text("Произошла ошибка при создании заказа. Попробуйте снова.")
        return

    # Рассчитываем длительность заказа
    total_minutes = order.total_duration_minutes
    hours = total_minutes // 60
    minutes = total_minutes % 60
    duration_text = f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"

    user_data_text = (
        f"Количество комнат: {rooms}\n"
        f"Количество санузлов: {bathrooms}\n"
        f"Частота уборки: {frequency}\n"
        f"Скидка: {int(discount_percentage * 100)}%\n"
        f"Дополнительные услуги:\n{services_text if selected_services else 'Не выбраны'}\n"
        f"Финальная цена: {final_price} BYN\n"
        f"Общее время выполнения: {duration_text}\n"
        f"Заказ №{order.id} был успешно оформлен!"
    )

    user_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Главное меню")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=user_data_text,
        reply_markup=user_keyboard
    )

    # Отправка сообщения в группу
    group_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Принять", callback_data=f'accept_{order.id}')]
    ])

    group_chat_id = '-1002462372782'
    group_message = (
        f"Заказ №{order.id} оформлен пользователем {customer.name}.\n"
        f"Дата выполнения: {scheduled_time}\n"
        f"Финальная цена: {final_price} BYN\n"
        f"Общее время выполнения: {duration_text}\n"
        f"----------------------------------------------------\n"
        f"Детали заказа:\n"
        f"Количество комнат: {rooms}\n"
        f"Количество санузлов: {bathrooms}\n"
        f"Выбранные услуги:\n{services_text if selected_services else 'Не выбраны'}\n"
        f"----------------------------------------------------\n"
        f"Необходима проверка и подтверждение заказа."
    )

    try:
        message = await context.bot.send_message(chat_id=group_chat_id, text=group_message, reply_markup=group_keyboard)

        # Запуск таймера
        asyncio.create_task(handle_order_timer(context, order.id, message.message_id, group_chat_id))
    except telegram.error.Forbidden as e:
        print(f"Ошибка отправки сообщения в группу: {e}")

async def handle_order_timer(context: CallbackContext, order_id: int, message_id: int, group_chat_id: str):
    await asyncio.sleep(3600)  # Ожидание 1 часа (3600 секунд)

    # Проверка статуса заказа
    order = await Order.objects.aget(id=order_id)
    if order.status != 'В ожидании':  # Если заказ уже принят, завершить
        return

    # Поиск доступного сотрудника
    total_time_in_hours = Decimal(order.total_duration_minutes) / Decimal(60)

    personnel = await Personnel.objects.order_by('hours_worked_week').filter(
        hours_worked_today__lte=Decimal(10) - total_time_in_hours,
        hours_worked_week__lte=Decimal(40) - total_time_in_hours
    ).afirst()

    if personnel:
        # Назначение заказа
        order.personnel = personnel
        order.status = 'В процессе'
        await order.asave()

        # Обновление времени работы сотрудника
        personnel.hours_worked_today += total_time_in_hours
        await personnel.asave()

        # Уведомление группы о назначении заказа
        group_message = (
            f"Заказ №{order.id} автоматически назначен сотруднику {personnel.nickname} "
            f"из-за отсутствия подтверждения.\n"
            f"Дата выполнения: {order.scheduled_time}\n"
            f"Финальная цена: {order.total_price} BYN\n"
            f"Общее время выполнения: {order.total_duration_minutes // 60} ч {order.total_duration_minutes % 60} мин."
        )
        try:
            await context.bot.edit_message_text(chat_id=group_chat_id, message_id=message_id, text=group_message)
        except telegram.error.Forbidden as e:
            print(f"Ошибка обновления сообщения: {e}")
    else:
        # Если нет доступного сотрудника, оставляем заказ в статусе "В ожидании"
        group_message = "К сожалению, нет доступных сотрудников для выполнения этого заказа."
        try:
            await context.bot.edit_message_text(chat_id=group_chat_id, message_id=message_id, text=group_message)
        except telegram.error.Forbidden as e:
            print(f"Ошибка обновления сообщения: {e}")

async def handle_accept_order(update: Update, context: CallbackContext):
    query = update.callback_query
    order_id = int(query.data.split('_')[1])  # Извлекаем order.id из callback_data

    # Получаем заказ асинхронно
    order = await sync_to_async(Order.objects.get)(id=order_id)
    if not order or order.status != 'В ожидании':
        await query.message.edit_text("Этот заказ уже принят или не существует.")
        return

    # Получаем работника, который нажал кнопку "Принять"
    personnel = await sync_to_async(Personnel.objects.get)(telegram_id=query.from_user.id)

    # Рассчитываем общее время для заказа (без добавления часов)
    total_duration_minutes = order.total_duration_minutes
    travel_time_minutes = order.travel_time_minutes
    total_time_in_hours = Decimal(total_duration_minutes + travel_time_minutes * 2) / Decimal(60)

    # Проверка лимитов времени
    if (
            personnel.hours_worked_today + total_time_in_hours > Decimal(10) or
            personnel.hours_worked_week + total_time_in_hours > Decimal(40)
    ):
        # Отправка уведомления пользователю, что он не может принять заказ
        await query.answer(text="Вы не можете принять этот заказ, так как он превышает лимит рабочего времени.", show_alert=True)
        return

    # Если работник может принять заказ, обновляем статус заказа
    order.personnel = personnel
    order.status = 'В процессе'
    await sync_to_async(order.save)()

    # Записываем текущее время принятия заказа в last_order_end_time для работника
    local_time = timezone.localtime(timezone.now())  # Получаем локальное время
    personnel.last_order_end_time = local_time  # Записываем время принятия
    await sync_to_async(personnel.save)()  # Сохраняем изменения

    # Создание новой клавиатуры с кнопками "Отменить" и "Завершить"
    new_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Отменить", callback_data=f'cancel_{order.id}')],
        [InlineKeyboardButton("Завершить", callback_data=f'complete_{order.id}')]
    ])

    # Уведомление для группы о принятии заказа
    group_chat_id = '-1002462372782'  # Укажите правильный chat_id вашей группы
    group_message = (
        f"Заказ №{order.id} принят сотрудником {personnel.nickname}.\n"
        f"Дата выполнения: {order.scheduled_time}\n"
        f"Финальная цена: {order.total_price} BYN\n"
        f"Общее время выполнения: {order.total_duration_minutes // 60} ч {order.total_duration_minutes % 60} мин\n"
        f"Статус: В процессе"
    )

    try:
        # Редактируем сообщение с новыми кнопками
        await context.bot.edit_message_text(
            chat_id=group_chat_id,
            message_id=query.message.message_id,
            text=group_message,
            reply_markup=new_keyboard
        )
    except telegram.error.Forbidden as e:
        print(f"Ошибка обновления сообщения: {e}")

# Модификация для асинхронной работы со связанными объектами
async def handle_cancel_order(update: Update, context: CallbackContext):
    query = update.callback_query
    order_id = int(query.data.split('_')[1])  # Извлекаем order.id из callback_data

    # Получаем заказ асинхронно
    order = await sync_to_async(Order.objects.get)(id=order_id)
    if not order or order.status != 'В процессе':
        await query.answer(text="Этот заказ не в процессе или уже завершён.", show_alert=True)
        return

    # Получаем работника, который нажал кнопку "Отменить"
    personnel = await sync_to_async(Personnel.objects.get)(telegram_id=query.from_user.id)

    # Получаем связанный объект personnel асинхронно
    order_personnel = await sync_to_async(lambda: order.personnel)()  # Используем sync_to_async для связанных объектов

    # Проверяем, что этот работник принял заказ
    if order_personnel.telegram_id != personnel.telegram_id:
        await query.answer(text="Вы не можете отменить этот заказ, так как вы не приняли его.", show_alert=True)
        return

    # Обновляем статус заказа
    order.status = 'Отменено'
    await sync_to_async(order.save)()

    # Уведомление для группы об отмене заказа
    group_chat_id = '-1002462372782'  # Укажите правильный chat_id вашей группы
    group_message = (
        f"Заказ №{order.id} был отменён сотрудником {personnel.nickname}.\n"
        f"Дата выполнения: {order.scheduled_time}\n"
        f"Финальная цена: {order.total_price} BYN\n"
        f"Общее время выполнения: {order.total_duration_minutes // 60} ч {order.total_duration_minutes % 60} мин\n"
        f"Статус: Отменён"
    )

    try:
        # Редактируем сообщение с обновлённым статусом
        await context.bot.edit_message_text(
            chat_id=group_chat_id,
            message_id=query.message.message_id,
            text=group_message
        )
    except telegram.error.Forbidden as e:
        print(f"Ошибка обновления сообщения: {e}")

# Ожидаем, что эти функции будут работать асинхронно
async def get_personnel(personnel_id):
    return await sync_to_async(Personnel.objects.get)(id=personnel_id)

async def handle_complete_order(update: Update, context: CallbackContext):
    query = update.callback_query
    order_id = int(query.data.split('_')[1])  # Извлекаем order.id из callback_data

    # Получаем заказ с использованием sync_to_async
    order = await sync_to_async(Order.objects.get)(id=order_id)
    if not order or order.status != 'В процессе':
        await query.answer(text="Этот заказ не в процессе или уже завершён.", show_alert=True)
        return

    # Получаем работника, который нажал кнопку "Завершить"
    personnel = await sync_to_async(Personnel.objects.get)(telegram_id=query.from_user.id)

    # Получаем personnel для проверки через sync_to_async
    order_personnel = await sync_to_async(lambda: order.personnel)()

    # Проверяем, что этот работник принял заказ
    if order_personnel.telegram_id != personnel.telegram_id:
        await query.answer(text="Вы не можете завершить этот заказ, так как вы не приняли его.", show_alert=True)
        return

    # Обновляем статус заказа
    order.status = 'Завершено'

    # Получаем локальное время в Минске
    local_time = timezone.localtime(timezone.now())

    # Заполняем поле end_time
    order.end_time = local_time  # Устанавливаем правильное время завершения заказа

    await sync_to_async(order.save)()

    # Рассчитываем общее время, которое работник потратил на выполнение этого заказа
    total_duration_minutes = order.total_duration_minutes
    travel_time_minutes = order.travel_time_minutes
    total_time_in_hours = Decimal(total_duration_minutes + travel_time_minutes * 2) / Decimal(60)

    # Добавляем это время к общему рабочему времени сотрудника
    personnel.hours_worked_today += total_time_in_hours
    await sync_to_async(personnel.save)()

    # Уведомление для группы о завершении заказа
    group_chat_id = '-1002462372782'  # Укажите правильный chat_id вашей группы
    group_message = (
        f"Заказ №{order.id} был завершён сотрудником {personnel.nickname}.\n"
        f"Дата выполнения: {order.scheduled_time}\n"
        f"Финальная цена: {order.total_price} BYN\n"
        f"Общее время выполнения: {order.total_duration_minutes // 60} ч {order.total_duration_minutes % 60} мин\n"
        f"Статус: Завершён"
    )

    try:
        # Редактируем сообщение с обновлённым статусом
        await context.bot.edit_message_text(
            chat_id=group_chat_id,
            message_id=query.message.message_id,
            text=group_message
        )
    except telegram.error.Forbidden as e:
        print(f"Ошибка обновления сообщения: {e}")

@sync_to_async
def add_personnel_to_db(update, phone_number=None, email=None):
    try:
        # Получаем chat_id группы
        chat_id = str(update.message.chat.id)  # ID чата (группы)

        # Проверяем, добавлен ли новый пользователь
        for new_member in update.message.new_chat_members:
            # Получаем chat_id и nickname для нового пользователя
            new_member_chat_id = str(new_member.id)
            new_member_nickname = new_member.username if new_member.username else f"User_{new_member.id}"  # Если нет username, используем ID

            # Проверяем, существует ли уже персонал с таким ID
            personnel, created = Personnel.objects.get_or_create(
                telegram_id=new_member_chat_id,  # Используем chat_id нового пользователя как уникальный идентификатор
                defaults={
                    'nickname': new_member_nickname,
                    'phone_number': None,  # Устанавливаем пустое значение для номера телефона
                    'email': email or 'notprovided@example.com',  # Если email не передается, то будет использовано значение по умолчанию
                }
            )

            if not created:
                # Если запись уже существует, обновляем её
                personnel.nickname = new_member_nickname
                personnel.phone_number = phone_number or personnel.phone_number  # Если не передан новый номер телефона, оставляем старый
                personnel.email = email or personnel.email  # Аналогично для email
                personnel.save()

    except IntegrityError as e:
        print(f"Ошибка при добавлении работника: {e}")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")

# Обработчик для отмены
async def cancel_order(update: Update, context: CallbackContext):
    query = update.callback_query

    # Логирование
    print("Кнопка отмены была нажата")

    # Очистка всех данных, связанных с заказом
    context.user_data.clear()

    # Отправляем сообщение, что заказ был отменен
    await query.message.edit_text("Вы отменили заказ. Если хотите, можете выбрать его снова.")

    # Возвращаем пользователя в главное меню
    reply_markup = main_menu()  # Не забудьте про вашу функцию main_menu()
    welcome_text = "Вы вернулись в главное меню. Выберите нужную опцию."

    # Используем send_message вместо answer
    await query.message.chat.send_message(welcome_text, reply_markup=reply_markup)

# Обработчик для ответа "Нет"
async def confirm_data_no(update: Update, context: CallbackContext) -> None:
    # Создаём клавиатуру с кнопками "Перейти в профиль" и "Калькулятор"
    keyboard = [
        [
            InlineKeyboardButton("Перейти в профиль", callback_data="go_to_profile"),
            InlineKeyboardButton("Выбор адреса", callback_data="go_to_address_selection")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с кнопками
    await update.callback_query.message.reply_text(
        'Для изменения персональных данных перейдите в "Профиль" и внесите необходимые изменения,' 
        'затем вернитесь к оформлению услуги.\n\n'
        'Или выберите другой адрес и заново рассчитайте комнаты.',
        reply_markup=reply_markup
    )

# Обработчик для выбора действия при нажатии на кнопки "Перейти в профиль" или "Калькулятор"
async def handle_confirm_data_no_choice(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'go_to_profile':
        # Переход в профиль
        await profile(update, context)
    elif query.data == 'go_to_address_selection':
        # Возвращение в калькулятор
        await call_cleaning(update, context)

# Обработчик для выбора времени уборки
async def handle_time_choice(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # Получаем выбранное время из callback_data
    time_choice = query.data.replace("time_", "")

    # Отправляем подтверждение выбранного времени
    await query.message.reply_text(f"Вы выбрали время уборки: {time_choice}")

# Обработчик для удаления адреса
async def delete_address(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    address_id = query.data.split("_")[1]

    await sync_to_async(Address.objects.filter(id=address_id).delete)()
    await query.edit_message_text("Адрес успешно удалён!")
    await show_addresses(update, context)

# Обработчик для изменения адреса
async def edit_address(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    address_id = query.data.split("_")[1]

    context.user_data["editing_address_id"] = address_id
    await query.edit_message_text("Введите новый адрес:")

# Функция для обновления рабочих часов
def update_work_hours():
    personnel_list = Personnel.objects.all()
    for personnel in personnel_list:
        personnel.hours_worked_week += personnel.hours_worked_today
        personnel.hours_worked_today = 0
        personnel.save()
    print(f"Work hours updated for all personnel at {timezone.now()}")

async def distribute_daily_equipment():
    bot = Bot(token=API_TOKEN)
    today = date.today()

    # Use sync_to_async to fetch data from the ORM
    personnel_list = await sync_to_async(list)(Personnel.objects.all())

    for person in personnel_list:
        # Use sync_to_async to filter orders
        orders_today = await sync_to_async(list)(
            person.orders.filter(scheduled_time__date=today, status__in=['В процессе', 'Завершено'])
        )

        if not orders_today:
            continue

        daily_inventory = await sync_to_async(DailyInventory.objects.create)(
            date=today,
            personnel=person,
            status=False
        )

        equipment_list = await sync_to_async(list)(Equipment.objects.all())
        issued_equipment = []  # Для формирования сообщения с выданным оборудованием

        for equipment in equipment_list:
            if equipment.quantity > 0:
                if equipment.type == 'Многоразовое':
                    await sync_to_async(EquipmentUsage.objects.create)(
                        daily_inventory=daily_inventory,
                        equipment=equipment,
                        quantity_used=1
                    )
                    issued_equipment.append((equipment.name, 1))  # Сохраняем данные для сообщения
                    equipment.quantity -= 1
                elif equipment.type == 'Одноразовое':
                    if len(orders_today) <= equipment.quantity:
                        await sync_to_async(EquipmentUsage.objects.create)(
                            daily_inventory=daily_inventory,
                            equipment=equipment,
                            quantity_used=len(orders_today)
                        )
                        issued_equipment.append((equipment.name, len(orders_today)))
                        equipment.quantity -= len(orders_today)
                    else:
                        message = f"Недостаточно {equipment.name} для ваших заказов."
                        await bot.send_message(
                            chat_id=person.telegram_id,
                            text=message
                        )
                        logger.info(f"Sent message to {person.telegram_id}: {message}")

                await sync_to_async(equipment.save)()

        # Формируем сообщение с перечнем выданного оборудования
        if issued_equipment:
            equipment_details = "\n".join(
                [f"- {name}: {quantity} шт." for name, quantity in issued_equipment]
            )
            message = (
                f"Оборудование на день выдано! Вот список:\n\n"
                f"{equipment_details}\n\n"
                f"Проверяйте ваш инвентарь."
            )
            await bot.send_message(
                chat_id=person.telegram_id,
                text=message
            )
            logger.info(f"Sent daily equipment message to {person.telegram_id}: {message}")

async def return_daily_equipment():
    bot = Bot(token=API_TOKEN)
    today = date.today()

    # Fetch inventories with pending return asynchronously
    daily_inventories = await sync_to_async(list)(
        DailyInventory.objects.filter(date=today, status=False).select_related('personnel')
    )

    for inventory in daily_inventories:
        # Fetch related equipment usages asynchronously
        equipment_usages = await sync_to_async(list)(
            EquipmentUsage.objects.filter(daily_inventory=inventory).select_related('equipment')
        )

        returned_items = []  # To store information about returned equipment

        for usage in equipment_usages:
            # Fetch related equipment
            equipment = usage.equipment
            if equipment.type == 'Многоразовое':
                # Update equipment quantity and returned_quantity
                equipment.quantity += usage.quantity_used
                usage.returned_quantity = usage.quantity_used

                # Save updated equipment quantity and usage asynchronously
                await sync_to_async(equipment.save)()
                await sync_to_async(usage.save)()

                # Add to the list of returned items
                returned_items.append(
                    f"{equipment.name} (Количество: {usage.quantity_used})"
                )

        # Mark inventory as returned asynchronously
        inventory.status = True
        await sync_to_async(inventory.save)()

        # Use personnel's telegram_id safely
        if hasattr(inventory.personnel, 'telegram_id'):
            # Create a detailed message with returned equipment info
            returned_items_str = "\n".join(returned_items)
            message = (
                "Многоразовое оборудование успешно возвращено!\n"
                "Список возвращённого оборудования:\n"
                f"{returned_items_str}"
            )
            await bot.send_message(
                chat_id=inventory.personnel.telegram_id,
                text=message
            )
            logger.info(f"Sent return confirmation to {inventory.personnel.telegram_id}: {message}")
        else:
            logger.warning(f"Telegram ID отсутствует у пользователя {inventory.personnel}.")

async def distribute_daily_equipment_wrapper():
    await distribute_daily_equipment()

def run_async_job(*args):
    # No need to use *args, we are passing distribute_daily_equipment_wrapper without arguments
    asyncio.run(distribute_daily_equipment_wrapper())

def return_daily_equipment_wrapper():
    asyncio.run(return_daily_equipment())

def main() -> None:
    application = Application.builder().token(API_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Профиль)$'), profile))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(О нас)$'), handle_about_us))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Техническая поддержка)$'), handle_technical_support))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Вызов клининга)$'), call_cleaning))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Список услуг)$'), show_services))
    application.add_handler(CallbackQueryHandler(service_info, pattern=r'^service_\d+$'))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^⬅️ Назад$"), handle_back))
    application.add_handler(CallbackQueryHandler(show_services, pattern="^back_to_services$"))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(
        '^(Сменить все контактные данные|Адреса|История заказов|Главное меню)$'), handle_profile_action))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Добавить|Назад)$'), handle_address_action))
    application.add_handler(CallbackQueryHandler(show_calculator, pattern="^address_cleaning_"))
    application.add_handler(CallbackQueryHandler(handle_address_choice, pattern="^address_"))
    application.add_handler(CallbackQueryHandler(handle_calculator,
                                                 pattern="^(decrease_rooms|increase_rooms|decrease_bathrooms|increase_bathrooms|next|back_to_call_cleaning)$"))
    application.add_handler(CallbackQueryHandler(delete_address, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(edit_address, pattern="^edit_"))
    application.add_handler(MessageHandler(filters.TEXT, handle_new_data))
    application.add_handler(CallbackQueryHandler(handle_next_step, pattern='^next$'))
    application.add_handler(CallbackQueryHandler(confirm_data_yes, pattern='^confirm_data_yes$'))
    application.add_handler(CallbackQueryHandler(confirm_data_no, pattern='^confirm_data_no$'))
    application.add_handler(
        CallbackQueryHandler(handle_confirm_data_no_choice, pattern="^go_to_profile|go_to_address_selection$"))

    # Здесь убираем pattern, чтобы обработчик мог правильно захватить данные от календаря
    application.add_handler(CallbackQueryHandler(calendar_handler, pattern='^cbcal_'))
    application.add_handler(CallbackQueryHandler(time_selection_handler, pattern='^time_'))

    application.add_handler(
        CallbackQueryHandler(handle_next_step_after_choosing_date, pattern='^next_step_after_date$'))

    application.add_handler(CallbackQueryHandler(handle_service_selection, pattern="^service_"))
    application.add_handler(CallbackQueryHandler(handle_choosing_discount, pattern="^next_step$"))

    application.add_handler(CallbackQueryHandler(handle_frequency_choice,
                                                 pattern="^(frequency_weekly|frequency_biweekly|frequency_monthly|frequency_once)$"))

    application.add_handler(CallbackQueryHandler(cancel_order, pattern='^cancel_order$'))
    application.add_handler(CallbackQueryHandler(handle_confirm_order, pattern='^confirm_order$'))

    application.add_handler(CallbackQueryHandler(handle_accept_order, pattern='^accept_'))
    application.add_handler(CallbackQueryHandler(handle_cancel_order, pattern='^cancel_'))
    application.add_handler(CallbackQueryHandler(handle_complete_order, pattern='^complete_'))

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, add_personnel_to_db))

    application.add_handler(CallbackQueryHandler(handle_back_after_about_us, pattern='^back_after_about_us$'))

    application.add_handler(CallbackQueryHandler(handle_back_after_about_us, pattern='^back_after_about_us$'))

    application.add_handler(CallbackQueryHandler(show_order_info, pattern='^order_'))

    application.add_handler(CallbackQueryHandler(handle_rate_order, pattern='^rate_'))
    application.add_handler(CallbackQueryHandler(handle_rate_order))
    application.add_handler(CallbackQueryHandler(handle_rating, pattern=r'^rating_\d+_\d+$'))
    application.add_handler(CallbackQueryHandler(handle_comment, pattern="^comment_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment_input))

    # Настройка расписания с использованием APScheduler
    scheduler = BackgroundScheduler()

    # Настройка ежедневного выполнения задачи в 23:59
    scheduler.add_job(
        update_work_hours,
        CronTrigger(hour=23, minute=59, second=0, timezone=timezone.get_current_timezone()),
        id='update_work_hours',
        replace_existing=True
    )

    # Запланировать выдачу оборудования на 9:00
    scheduler.add_job(
        run_async_job,
        CronTrigger(hour=9, minute=0),
        id="distribute_equipment",
        replace_existing=True
    )

    # Запланировать возврат оборудования на 18:00
    scheduler.add_job(
        lambda: asyncio.run(return_daily_equipment()),
        CronTrigger(hour=18, minute=0),
        id="return_equipment",
        replace_existing=True
    )

    # Запуск планировщика
    scheduler.start()

    application.run_polling()

if __name__ == '__main__':
    main()
