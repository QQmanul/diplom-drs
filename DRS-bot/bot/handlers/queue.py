import logging
import aiohttp
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram

from config import API_BASE_URL

logger = logging.getLogger(__name__)

async def update_queue_item_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для обновления статуса встречи в очереди"""
    query = update.callback_query
    await query.answer()
    
    # Получаем данные из callback_data
    data = query.data.split(':')
    item_id = data[1]
    new_status = int(data[2])
    
    token = context.user_data.get('token')
    if not token:
        await query.message.edit_text("Пожалуйста, авторизуйтесь.")
        return

    try:
        url = f"{API_BASE_URL}/api/queue_items/{item_id}"
        headers = {'Authorization': f'Bearer {token}'}
        payload = {"newStatusId": new_status}
        
        logger.info(f"Отправка PATCH запроса на {url} для обновления статуса встречи {item_id} на {new_status}")
        
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=payload, headers=headers) as response:
                if response.status in [200, 204]:  # 204 No Content тоже считается успехом
                    logger.info(f"Статус встречи {item_id} успешно обновлен на {new_status}")
                    # После успешного обновления статуса обновляем отображение очереди
                    await show_queue(update, context)
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to update queue item status: {response.status} - {error_text}")
                    await query.message.edit_text(
                        f"Ошибка при обновлении статуса встречи (код {response.status}).",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]])
                    )
    except Exception as e:
        logger.error(f"Error updating queue item status: {e}", exc_info=True)
        await query.message.edit_text(
            "Произошла ошибка при обновлении статуса встречи.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]])
        )

async def show_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id_telegram = update.effective_user.id 
    
    token = context.user_data.get('token')
    
    logger.info(f"User {user_id_telegram} - In show_queue. Token in context: {bool(token)}")
    if token:
        logger.debug(f"User {user_id_telegram} - Token (partial for log): Bearer {token[:15]}...{token[-15:]}")
    else:
        await query.message.edit_text("Пожалуйста, авторизуйтесь (токен отсутствует).")
        return
    
    role = context.user_data.get('role')
    if role not in ['Секретарь', 'Принимающее лицо', 'Администратор']:
        await query.message.edit_text("У вас нет прав для просмотра этой информации.")
        return

    receiver_api_id = context.user_data.get('user_id_from_db') 
    if not receiver_api_id:
        logger.error(f"API user ID (receiver_api_id) not found in context for user {user_id_telegram} to view queue.")
        await query.message.edit_text("Ошибка: не удалось определить ваш ID для просмотра очереди. Попробуйте войти снова.")
        return

    queue_endpoint = f"{API_BASE_URL}/api/receivers/{receiver_api_id}/queue"
    
    logger.info(f"User {user_id_telegram} (Role: {role}, API ID: {receiver_api_id}) - Attempting to fetch queue from {queue_endpoint}.")

    try:
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {token}'} 
            logger.debug(f"User {user_id_telegram} - Requesting {queue_endpoint} with headers: {headers.keys()}") 

            async with session.get(queue_endpoint, headers=headers) as response:
                response_status = response.status
                response_body_text = await response.text() 

                if response_status == 200:
                    try:
                        queue_items = await response.json() 
                        logger.info(f"Received queue items: {len(queue_items)} items")
                        
                        # Фильтруем завершенные встречи
                        filtered_queue_items = [
                            item for item in queue_items 
                            if item.get('statusId') not in [4, 5]  # 4 = Завершено, 5 = Пропущено
                        ]
                        
                        # Сортируем по позиции
                        filtered_queue_items.sort(key=lambda x: x.get('position', 0))
                        
                        logger.info(f"Filtered and sorted queue items: {len(filtered_queue_items)} items (excluding completed)")
                        
                        for idx, item in enumerate(filtered_queue_items, 1):
                            logger.info(f"Queue item {idx}: ID={item.get('id')}, Position={item.get('position')}, Status={item.get('statusName')} (ID: {item.get('statusId')}), Visitor={item.get('visitorFullName')}")
                    except aiohttp.ContentTypeError: 
                        logger.error(f"Queue endpoint {queue_endpoint} returned 200 but content is not JSON. Body: {response_body_text}")
                        await query.message.edit_text("Ошибка: получен неверный формат данных от сервера.", 
                                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
                        return
                    
                    if not isinstance(filtered_queue_items, list):
                        logger.error(f"Unexpected queue data format from {queue_endpoint}. Expected a list, got {type(filtered_queue_items)}: {filtered_queue_items}")
                        await query.message.edit_text("Ошибка: неверный формат данных очереди.", 
                                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
                        return

                    if not filtered_queue_items:
                        msg = "В вашей очереди нет активных посетителей."
                        keyboard = [[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]
                    else:
                        msg = f"👥 Ваша текущая очередь:\n\n"
                        keyboard = []
                        
                        for idx, item in enumerate(filtered_queue_items, 1):
                            position = item.get('position', 0)
                            status_name = item.get('statusName', 'Неизвестно')
                            visitor_name = item.get('visitorFullName', 'Неизвестно')
                            msg += f"{idx}. {visitor_name} (Позиция: {position})\n"
                            msg += f"   Статус: {status_name}\n\n"
                            
                            # Добавляем кнопки управления для первой встречи в списке
                            if idx == 1:  # Changed from position == 1 to idx == 1
                                item_id = item.get('id')
                                if item_id:
                                    status_id = item.get('statusId', 0)
                                    logger.info(f"Adding control buttons for first queue item: ID={item_id}, Status ID={status_id}")
                                    if status_id == 1:  # Ожидание
                                        logger.info("Adding buttons for 'Waiting' status")
                                        keyboard.extend([
                                            [
                                                InlineKeyboardButton("▶️ Начать встречу", callback_data=f"queue_status:{item_id}:2"),
                                                InlineKeyboardButton("⏸ Перерыв", callback_data=f"queue_status:{item_id}:3")
                                            ],
                                            [
                                                InlineKeyboardButton("❌ Пропустить", callback_data=f"queue_status:{item_id}:5")
                                            ]
                                        ])
                                    elif status_id == 2:  # В процессе
                                        keyboard.extend([
                                            [
                                                InlineKeyboardButton("✅ Завершить", callback_data=f"queue_status:{item_id}:4"),
                                                InlineKeyboardButton("⏸ Перерыв", callback_data=f"queue_status:{item_id}:3")
                                            ]
                                        ])
                                    elif status_id == 3:  # Перерыв
                                        keyboard.extend([
                                            [
                                                InlineKeyboardButton("▶️ Продолжить", callback_data=f"queue_status:{item_id}:2"),
                                                InlineKeyboardButton("❌ Пропустить", callback_data=f"queue_status:{item_id}:5")
                                            ]
                                        ])
                        
                        keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data='show_queue')])
                        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')])
                    
                    try:
                        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
                    except telegram.error.BadRequest as e:
                        if "Message is not modified" in str(e):
                            # If the message hasn't changed, just answer the callback query silently
                            await query.answer("Очередь не изменилась")
                        else:
                            # If it's a different error, re-raise it
                            raise
                else: 
                    logger.error(f"Failed to get queue from {queue_endpoint} for receiver {receiver_api_id}: {response_status} - Body: {response_body_text}")
                    if response_status == 401:
                         await query.message.edit_text("Ошибка аутентификации (401). Пожалуйста, попробуйте войти в систему снова (/logout, затем /start).", 
                                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
                    elif response_status == 403:
                         await query.message.edit_text("Доступ запрещен (403). У вас нет прав для просмотра этой очереди.", 
                                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
                    elif response_status == 404:
                        await query.message.edit_text("Не удалось найти очередь для вас (404). Возможно, она еще не создана или у вас нет назначенной очереди.", 
                                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
                    else:
                        await query.message.edit_text(f"Не удалось загрузить очередь (ошибка {response_status}).", 
                                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
    except Exception as e:
        logger.error(f"Exception in show_queue function for receiver {receiver_api_id}: {e}", exc_info=True)
        await query.message.edit_text("Произошла критическая ошибка при загрузке очереди.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))