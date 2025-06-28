import logging
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from config import API_BASE_URL
from bot.database import Database
from .states import AWAITING_LOGIN_CREDENTIALS
from .common import show_main_menu

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start command received from user {update.effective_user.id}")
    db = Database()
    user_data_db = db.get_user_auth(update.effective_user.id)
    
    context.user_data.clear()
    context.user_data['state'] = None

    if user_data_db:
        logger.info(f"Found saved auth data for user {update.effective_user.id}")
        token = user_data_db['token']
        context.user_data['token'] = token
        
        # Fetch fresh user data from API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_BASE_URL}/api/Users/me",
                    headers={"Authorization": f"Bearer {token}"}
                ) as response:
                    if response.status == 200:
                        user_profile = await response.json()
                        context.user_data['role'] = user_profile.get('roleName')
                        context.user_data['user_id_from_db'] = user_profile.get('id')
                        context.user_data['full_name'] = user_profile.get('fullName')
                        
                        if 'signalr_client' in context.bot_data:
                            signalr_client = context.bot_data.get('signalr_client')
                            if signalr_client:
                                try:
                                    await signalr_client.start_connection(update.effective_user.id, token)
                                except Exception as e:
                                    logger.error(f"SignalR connection error on start: {e}")
                        
                        await update.message.reply_text(f"👋 С возвращением, {user_profile.get('fullName')}!")
                        await show_main_menu(update, context, user_profile.get('roleName'))
                    else:
                        logger.error(f"Failed to fetch user profile: {response.status}")
                        context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
                        await update.message.reply_text(
                            "Сессия истекла. Пожалуйста, войдите снова, введя ваш email и пароль, разделенные пробелом (например: user@example.com ваш_пароль):"
                        )
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
            await update.message.reply_text(
                "Произошла ошибка при получении данных профиля. Пожалуйста, войдите снова, введя ваш email и пароль, разделенные пробелом (например: user@example.com ваш_пароль):"
            )
    else:
        logger.info(f"No saved auth data for user {update.effective_user.id}, requesting login")
        context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
        await update.message.reply_text(
            "Добро пожаловать! Пожалуйста, введите ваш email и пароль для входа, разделенные пробелом (например: user@example.com ваш_пароль):"
        )

async def handle_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        credentials = update.message.text.strip().split()
        if len(credentials) != 2:
            await update.message.reply_text("Пожалуйста, введите email и пароль, разделенные пробелом.")
            return

        email_or_username, password = credentials
        api_login_payload = {"Email": email_or_username, "password": password}
        
        logger.info(f"Attempting login for: {email_or_username} using payload: {api_login_payload}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/api/auth/login",
                json=api_login_payload
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"Auth API error: {response.status} - {response_text}. Sent Payload: {api_login_payload}")
                    await update.message.reply_text("❌ Ошибка авторизации. Проверьте данные и попробуйте снова.")
                    context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
                    return

                auth_data = await response.json()
                token = auth_data.get('token')
                if not token:
                    logger.error(f"No token in auth response: {auth_data}")
                    await update.message.reply_text("❌ Ошибка авторизации: токен не получен.")
                    context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
                    return

                context.user_data['token'] = token

                # Get user data
                async with session.get(
                    f"{API_BASE_URL}/api/users/me",
                    headers={"Authorization": f"Bearer {token}"}
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Error getting user data: {response.status} - {response_text}")
                        await update.message.reply_text("❌ Ошибка получения данных пользователя.")
                        context.user_data.pop('token', None)
                        context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
                        return

                    user_data_api = await response.json()
                    user_id_api = user_data_api.get('id')
                    if not user_id_api:
                        logger.error(f"User ID not found in /users/me response: {user_data_api}")
                        await update.message.reply_text("❌ Ошибка: ID пользователя не найден в ответе API.")
                        context.user_data.pop('token', None)
                        context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
                        return

                    role = user_data_api.get('role', 'Посетитель')
                    full_name = user_data_api.get('fullName', email_or_username)

                    # Save to database
                    db = Database()
                    db.save_user_auth(
                        telegram_id=update.effective_user.id,
                        user_id=user_id_api,
                        token=token,
                        role=role,
                        full_name=full_name
                    )

                    context.user_data['role'] = role
                    context.user_data['user_id_from_db'] = user_id_api
                    logger.info(f"Saved user auth data to database for {full_name}")

                    if 'signalr_client' in context.bot_data:
                        signalr_client = context.bot_data.get('signalr_client')
                        if signalr_client:
                            try:
                                await signalr_client.start_connection(update.effective_user.id, token)
                            except Exception as e:
                                logger.error(f"SignalR connection error after auth: {e}")

                    await update.message.reply_text(f"✅ Успешная авторизация! Добро пожаловать, {full_name}!")
                    await show_main_menu(update, context, role)

    except Exception as e:
        logger.error(f"Auth error: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при авторизации. Попробуйте позже.")
        context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        token = context.user_data.get('token')
        
        if token:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{API_BASE_URL}/api/auth/logout",
                    headers={"Authorization": f"Bearer {token}"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Logout API error: {response.status} - {await response.text()}")
        
        # Clear user data
        context.user_data.clear()
        context.user_data['state'] = None
        
        # Remove from database
        db = Database()
        db.delete_user_auth(user_id)
        
        if 'signalr_client' in context.bot_data:
            signalr_client = context.bot_data.get('signalr_client')
            if signalr_client:
                try:
                    await signalr_client.stop_connection(user_id)
                except Exception as e:
                    logger.error(f"SignalR disconnection error on logout: {e}")
        
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.edit_text("✅ Вы успешно вышли из системы.")
        elif update.message:
            await update.message.reply_text("✅ Вы успешно вышли из системы.")
            
    except Exception as e:
        logger.error(f"Logout error: {e}", exc_info=True)
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.edit_text("⚠️ Ошибка при выходе из системы")
        elif update.message:
            await update.message.reply_text("⚠️ Ошибка при выходе из системы")