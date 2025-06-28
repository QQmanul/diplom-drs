import logging
import aiohttp
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import API_BASE_URL
from .states import (
    AWAITING_RECEIVER,
    AWAITING_TIME,
    AWAITING_DURATION,
    AWAITING_TOPIC
)
from .common import show_main_menu

logger = logging.getLogger(__name__)

async def show_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    token = context.user_data.get('token')
    if not token:
        await query.message.edit_text("Пожалуйста, авторизуйтесь.")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/api/appointments",
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status != 200:
                    logger.error(f"Error fetching appointments: {response.status} - {await response.text()}")
                    await query.message.edit_text("Ошибка загрузки встреч.")
                    return
                
                appointments_data = await response.json()
                appointments = appointments_data if isinstance(appointments_data, list) else appointments_data.get("items", [])
                
                if not appointments:
                    await query.message.edit_text(
                        "У вас пока нет встреч.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]])
                    )
                    return

                text_parts = ["📅 Ваши встречи:\n\n"]
                for idx, appointment in enumerate(appointments, 1):
                    try:
                        # Parse start and end times
                        start_time = datetime.fromisoformat(appointment.get('startTime', '').replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(appointment.get('endTime', '').replace('Z', '+00:00'))
                        
                        # Convert to Moscow time (UTC+3)
                        moscow_tz = timezone(timedelta(hours=3))
                        start_time_msk = start_time.astimezone(moscow_tz)
                        end_time_msk = end_time.astimezone(moscow_tz)
                        
                        # Format date and times
                        date_str = start_time_msk.strftime("%d.%m.%Y")
                        start_time_str = start_time_msk.strftime("%H:%M")
                        end_time_str = end_time_msk.strftime("%H:%M")
                        
                        text_parts.append(
                            f"{idx}. {appointment.get('topic', 'Без темы')}\n"
                            f"   📅 Дата: {date_str}\n"
                            f"   ⏰ Время: {start_time_str} - {end_time_str}\n"
                            f"   📊 Статус: {appointment.get('statusName', 'Не указан')}\n\n"
                        )
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error formatting appointment time: {e}")
                        text_parts.append(
                            f"{idx}. {appointment.get('topic', 'Без темы')}\n"
                            f"   ⚠️ Ошибка форматирования времени\n"
                            f"   📊 Статус: {appointment.get('statusName', 'Не указан')}\n\n"
                        )

                text = "".join(text_parts)
                if len(text) > 4090:
                    text = "Слишком много встреч для отображения. Показаны последние.\n" + text[:3800] + "..."

                await query.message.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]])
                )

    except Exception as e:
        logger.error(f"Appointments error: {e}", exc_info=True)
        await query.message.edit_text("Ошибка при загрузке встреч.")

async def create_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    token = context.user_data.get('token')
    if not token:
        await query.message.edit_text("Пожалуйста, авторизуйтесь.")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/api/Users/receivers",
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status != 200:
                    logger.error(f"Error fetching receivers: {response.status} - {await response.text()}")
                    await query.message.edit_text("Ошибка загрузки списка руководителей.")
                    return
                
                receivers = await response.json()
                if not receivers:
                    await query.message.edit_text("Нет доступных руководителей.")
                    return

                keyboard = []
                for receiver in receivers:
                    keyboard.append([
                        InlineKeyboardButton(
                            receiver.get('fullName', 'Имя не указано'),
                            callback_data=f"select_receiver_{receiver['id']}"
                        )
                    ])
                keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')])

                await query.message.edit_text(
                    "Выберите руководителя:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                context.user_data['state'] = AWAITING_RECEIVER

    except Exception as e:
        logger.error(f"Create appointment error: {e}", exc_info=True)
        await query.message.edit_text("Ошибка при создании встречи.")

async def handle_receiver_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        receiver_id = query.data.split('_')[-1]  # Get the UUID string directly
        context.user_data['selected_receiver_id'] = receiver_id
        
        await query.message.edit_text(
            "Введите время начала встречи в формате ДД.ММ.ГГГГ ЧЧ:ММ (например: 01.01.2024 14:30):"
        )
        context.user_data['state'] = AWAITING_TIME
        
    except Exception as e:
        logger.error(f"Receiver selection error: {e}", exc_info=True)
        await query.message.edit_text("Ошибка при выборе руководителя.")

async def handle_start_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        input_text = update.message.text.strip()
        logger.info(f"User {user_id} - Handling start time input: {input_text}")

        try:
            start_time = datetime.strptime(input_text, "%d.%m.%Y %H:%M")
            if start_time < datetime.now():
                await update.message.reply_text("Время начала встречи не может быть в прошлом. Введите корректное время:")
                context.user_data['state'] = AWAITING_TIME
                return
        except ValueError:
            await update.message.reply_text("Неверный формат времени. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ (например: 01.01.2024 14:30):")
            context.user_data['state'] = AWAITING_TIME
            return

        context.user_data['temp_start_time'] = start_time
        await update.message.reply_text(
            "Отлично! Теперь введите длительность встречи в минутах (например: 30, 45, 60):\n"
        )
        context.user_data['state'] = AWAITING_DURATION
        
    except Exception as e:
        logger.error(f"Start time input error for user {update.effective_user.id}: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке времени. Попробуйте еще раз.")
        context.user_data['state'] = AWAITING_TIME

async def handle_duration_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        input_text = update.message.text.strip()
        logger.info(f"User {user_id} - Handling duration input: {input_text}")

        temp_start_time = context.user_data.get('temp_start_time')
        if not temp_start_time:
            logger.error(f"User {user_id} - temp_start_time not found. Resetting.")
            await update.message.reply_text("Произошла ошибка, данные о времени начала утеряны. Начните сначала.")
            context.user_data['state'] = None
            await show_main_menu(update, context)
            return

        try:
            duration_minutes = int(input_text)
            if duration_minutes <= 0:
                await update.message.reply_text("Длительность должна быть положительным числом. Введите количество минут:")
                context.user_data['state'] = AWAITING_DURATION
                return
            
            context.user_data['appointment_payload'] = {
                'receiver_id': context.user_data['selected_receiver_id'],
                'start_time': temp_start_time.isoformat()
            }
            context.user_data['calculated_end_time'] = temp_start_time + timedelta(minutes=duration_minutes)
            context.user_data.pop('temp_start_time', None)
            
            await update.message.reply_text("Введите тему встречи:")
            context.user_data['state'] = AWAITING_TOPIC
            
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите число минут (например: 30):")
            context.user_data['state'] = AWAITING_DURATION
            
    except Exception as e:
        logger.error(f"Duration input error: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке длительности.")
        context.user_data['state'] = AWAITING_DURATION

async def handle_topic_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        topic = update.message.text.strip()
        logger.info(f"User {user_id} - Handling topic/title input: {topic}")

        if not topic:
            await update.message.reply_text("Тема/заголовок встречи не может быть пустой. Пожалуйста, введите тему:")
            context.user_data['state'] = AWAITING_TOPIC
            return

        appointment_payload = context.user_data.get('appointment_payload')
        if not appointment_payload:
            logger.error(f"User {user_id} - appointment_payload not found. Resetting.")
            await update.message.reply_text("Произошла ошибка: данные для создания встречи утеряны. Начните заново.")
            context.user_data['state'] = None
            await show_main_menu(update, context)
            return
            
        # Format the appointment data according to the API schema
        formatted_payload = {
            "receiverId": context.user_data['selected_receiver_id'],
            "startTime": appointment_payload['start_time'],
            "endTime": context.user_data['calculated_end_time'].isoformat(),
            "topic": topic
        }

        token = context.user_data.get('token')
        logger.info(f"User {user_id} - Attempting to create appointment. Payload: {formatted_payload}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/api/appointments",
                headers={"Authorization": f"Bearer {token}"},
                json=formatted_payload
            ) as response:
                if response.status == 201:
                    await update.message.reply_text("✅ Заявка на встречу успешно создана!")
                    logger.info(f"User {user_id} - Appointment request created successfully.")
                else:
                    response_text = await response.text()
                    logger.error(f"User {user_id} - Error creating appointment: {response.status} - {response_text}. Payload: {formatted_payload}")
                    await update.message.reply_text(f"❌ Ошибка при создании заявки (Код: {response.status}). Попробуйте позже.")
        
        context.user_data.pop('appointment_payload', None)
        context.user_data.pop('selected_receiver_id', None)
        context.user_data.pop('calculated_end_time', None)
        context.user_data['state'] = None
        await show_main_menu(update, context)
                
    except Exception as e:
        logger.error(f"Topic input or API call error for user {update.effective_user.id}: {e}", exc_info=True)
        await update.message.reply_text("Критическая ошибка при сохранении заявки. Попробуйте позже.")
        context.user_data['state'] = None
        await show_main_menu(update, context)

async def manage_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    token = context.user_data.get('token')
    if not token:
        await query.message.edit_text("Пожалуйста, авторизуйтесь.")
        return
    
    role = context.user_data.get('role')
    if role not in ['Секретарь', 'Принимающее лицо', 'Администратор']:
        await query.message.edit_text("У вас нет прав для управления встречами.")
        return
    
    try:
        logger.info(f"User {user_id} (Role: {role}) - Managing appointments (fetching list).")
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {token}'}
            async with session.get(f"{API_BASE_URL}/api/appointments", headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to get appointments for manager: {response.status} - {await response.text()}")
                    await query.message.edit_text("Не удалось загрузить список встреч.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]))
                    return

                appointments_data = await response.json()
                appointments = appointments_data if isinstance(appointments_data, list) else appointments_data.get("items", [])
                
                # Фильтруем встречи, исключая отмененные, завершенные и перенесенные
                filtered_appointments = [
                    app for app in appointments 
                    if app.get('statusName') not in ['Отменена', 'Завершена', 'Перенесена']
                ]
                
                if not filtered_appointments:
                    await query.message.edit_text("Нет активных встреч для управления.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]))
                    return

                text_parts = ["📋 Управление встречами:\n\n"]
                keyboard_buttons = []
                
                for appointment in filtered_appointments:
                    appointment_id = appointment.get('id')
                    if not appointment_id:
                        continue
                        
                    try:
                        # Parse and format times
                        start_time = datetime.fromisoformat(appointment.get('startTime', '').replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(appointment.get('endTime', '').replace('Z', '+00:00'))
                        
                        # Convert to Moscow time (UTC+3)
                        moscow_tz = timezone(timedelta(hours=3))
                        start_time_msk = start_time.astimezone(moscow_tz)
                        end_time_msk = end_time.astimezone(moscow_tz)
                        
                        # Format date and times
                        date_str = start_time_msk.strftime("%d.%m.%Y")
                        start_time_str = start_time_msk.strftime("%H:%M")
                        end_time_str = end_time_msk.strftime("%H:%M")
                        
                        text_parts.append(
                            #f"ID: {appointment_id}\n"
                            f"📝 Тема: {appointment.get('topic', 'Без темы')}\n"
                            f"👤 Посетитель: {appointment.get('visitorFullName', 'Имя не указано')}\n"
                            f"👥 Принимающий: {appointment.get('receiverFullName', 'Имя не указано')}\n"
                            f"📅 Дата: {date_str}\n"
                            f"⏰ Время: {start_time_str} - {end_time_str}\n"
                            f"📍 Место: {appointment.get('location', 'Не указано')}\n"
                            f"📊 Статус: {appointment.get('statusName', 'Не указан')}\n"
                            f"📎 Вложений: {len(appointment.get('attachments', []))}\n\n"
                        )
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error formatting appointment time: {e}")
                        text_parts.append(
                            #f"ID: {appointment_id}\n"
                            f"📝 Тема: {appointment.get('topic', 'Без темы')}\n"
                            f"👤 Посетитель: {appointment.get('visitorFullName', 'Имя не указано')}\n"
                            f"👥 Принимающий: {appointment.get('receiverFullName', 'Имя не указано')}\n"
                            f"⚠️ Ошибка форматирования времени\n"
                            f"📊 Статус: {appointment.get('statusName', 'Не указан')}\n\n"
                        )
                    
                    status = appointment.get('statusName', '')
                    if status == 'Запрошена':
                        keyboard_buttons.extend([
                            [
                                InlineKeyboardButton(f"✅ Одобрить {appointment.get('topic', 'Без темы')}", callback_data=f"app_action:approve:{appointment_id}"),
                                InlineKeyboardButton(f"❌ Отклонить {appointment.get('topic', 'Без темы')}", callback_data=f"app_action:cancel:{appointment_id}")
                            ]
                        ])
                    elif status == 'Подтверждена':
                        keyboard_buttons.append([
                            InlineKeyboardButton(f"❌ Отменить {appointment.get('topic', 'Без темы')}", callback_data=f"app_action:reject:{appointment_id}")
                        ])
                
                keyboard_buttons.append([InlineKeyboardButton("🔄 Обновить", callback_data='manage_appointments')])
                keyboard_buttons.append([InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')])
                
                text = "".join(text_parts)
                if len(text) > 4090:
                    text = "Слишком много встреч для отображения. Показаны последние.\n" + text[:3800] + "..."
                
                await query.message.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard_buttons)
                )
                
    except Exception as e:
        logger.error(f"Manage appointments error: {e}", exc_info=True)
        await query.message.edit_text("Ошибка при управлении встречами.")

async def handle_appointment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    try:
        # Parse the callback data
        parts = query.data.split(':')
        if len(parts) != 3:
            logger.error(f"Invalid callback data format: {query.data}")
            await query.message.edit_text("Ошибка в формате данных действия.")
            return
            
        action = parts[1]
        appointment_id = parts[2]
        
        logger.info(f"User {user_id} - Performing action '{action}' on appointment_id {appointment_id}")
        
        token = context.user_data.get('token')
        if not token:
            await query.message.edit_text("Пожалуйста, авторизуйтесь.")
            return
        
        status_map = {
            'approve': {'statusId': 2, 'statusName': 'Подтверждена'},
            'reject': {'statusId': 5, 'statusName': 'Перенесена'},
            'cancel': {'statusId': 3, 'statusName': 'Отменена'}
        }
        
        status_data = status_map.get(action)
        if not status_data:
            logger.error(f"Unknown action: {action}")
            await query.message.edit_text("Неизвестное действие.")
            return
        
        async with aiohttp.ClientSession() as session:
            async with session.patch(
                f"{API_BASE_URL}/api/Appointments/{appointment_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"statusId": status_data['statusId']}
            ) as response:
                if response.status in [200, 204]:  # Both 200 and 204 indicate success
                    await query.message.edit_text(f"✅ Статус встречи успешно изменен на '{status_data['statusName']}'.")
                    await manage_appointments(update, context)
                else:
                    response_text = await response.text()
                    logger.error(f"Error updating appointment status: {response.status} - {response_text}")
                    await query.message.edit_text(f"❌ Ошибка при изменении статуса встречи (Код: {response.status}).")
                    
    except Exception as e:
        logger.error(f"Appointment action error: {e}", exc_info=True)
        await query.message.edit_text("Ошибка при выполнении действия с встречей.")