import logging
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import API_BASE_URL

logger = logging.getLogger(__name__)

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        token = context.user_data.get('token')
        if not token:
            await query.message.edit_text("Сначала авторизуйтесь! Нажмите /start")
            return

        logger.info(f"User {user_id} - Fetching profile from /api/users/me.")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/api/users/me", 
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status != 200:
                    logger.error(f"Error fetching profile for user {user_id}: {response.status} - {await response.text()}")
                    await query.message.edit_text("Ошибка загрузки профиля.")
                    return
                
                user_data_api = await response.json()
                profile_text = (
                    f"👤 Ваш Профиль\n\n"
                    f"Имя: {user_data_api.get('fullName', user_data_api.get('full_name', 'Не указано'))}\n"
                    f"Email: {user_data_api.get('email', 'Не указан')}\n"
                    f"Роль: {user_data_api.get('roleName', user_data_api.get('role', 'Не указана'))}\n"
                    f"Телефон: {user_data_api.get('phone', 'Не указан')}" 
                )
                await query.message.edit_text(profile_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
    except Exception as e:
        logger.error(f"Profile error for user {user_id}: {e}", exc_info=True)
        await query.message.edit_text("Ошибка при загрузке профиля.")

async def handle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        token = context.user_data.get('token')
        if not token:
            await query.message.edit_text("Сначала авторизуйтесь! Нажмите /start")
            return

        logger.info(f"User {user_id} - Fetching notifications from /api/notifications.")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/api/notifications", 
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status != 200:
                    logger.error(f"Error fetching notifications for user {user_id}: {response.status} - {await response.text()}")
                    await query.message.edit_text("Ошибка загрузки уведомлений.")
                    return
                
                notifications_list = await response.json() 
                notifications = notifications_list if isinstance(notifications_list, list) else notifications_list.get("items", [])

                if not notifications:
                    text = "У вас нет непрочитанных уведомлений."
                else:
                    text = "🔔 Непрочитанные уведомления:\n\n"
                    for idx, notif in enumerate(notifications, 1):
                        text += f"{idx}. {notif.get('message', 'Нет текста уведомления')}\n"
                
                await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='main_menu')]]))
    except Exception as e:
        logger.error(f"Notifications error for user {user_id}: {e}", exc_info=True)
        await query.message.edit_text("Ошибка при загрузке уведомлений.")