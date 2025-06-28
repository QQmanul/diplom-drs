import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import Database
from .states import (
    AWAITING_LOGIN_CREDENTIALS,
    AWAITING_RECEIVER,
    AWAITING_TIME,
    AWAITING_DURATION,
    AWAITING_TOPIC
)

logger = logging.getLogger(__name__)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, role: str = None):
    query = update.callback_query
    effective_message = query.message if query else update.message
    
    if not role:
        # Try to get role from context first
        role = context.user_data.get('role')
        if not role:
            # If not in context, try database
            db = Database()
            user_data = db.get_user_auth(update.effective_user.id)
            if user_data:
                role = user_data.get('role')
                context.user_data['role'] = role
            else:
                logger.warning(f"Cannot show main menu, role unknown for user {update.effective_user.id}. Prompting login.")
                if query: await query.answer()
                await effective_message.reply_text("Пожалуйста, авторизуйтесь для доступа к меню. Нажмите /start")
                return

    if role == 'Администратор':
        keyboard = [
            [InlineKeyboardButton("➕ Создать встречу", callback_data='create_appointment')],
            [InlineKeyboardButton("✅ Управление встречами", callback_data='manage_appointments')],
            [InlineKeyboardButton("🚪 Выйти", callback_data='logout')]
        ]
    elif role in ['Секретарь', 'Принимающее лицо']:
        keyboard = [
            [InlineKeyboardButton("📅 Мои встречи", callback_data='my_appointments')],
            [InlineKeyboardButton("➕ Создать встречу", callback_data='create_appointment')],
            [InlineKeyboardButton("⏳ Очередь", callback_data='show_queue')],
            [InlineKeyboardButton("✅ Управление встречами", callback_data='manage_appointments')],
            [InlineKeyboardButton("👤 Профиль", callback_data='profile')],
            [InlineKeyboardButton("🚪 Выйти", callback_data='logout')]
        ]
    else:  # Посетитель or any other role
        print(role)
        keyboard = [
            [InlineKeyboardButton("📅 Мои встречи", callback_data='my_appointments')],
            [InlineKeyboardButton("➕ Создать встречу", callback_data='create_appointment')],
            [InlineKeyboardButton("👤 Профиль", callback_data='profile')],
            [InlineKeyboardButton("🚪 Выйти", callback_data='logout')]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_text = "Главное меню. Выберите действие:"

    if query:
        await query.answer()
        await query.message.edit_text(menu_text, reply_markup=reply_markup)
    else:
        await effective_message.reply_text(menu_text, reply_markup=reply_markup)
    context.user_data['state'] = None  # Clear state when showing main menu

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_state = context.user_data.get('state')
    user_id = update.effective_user.id
    message_text = update.message.text
    logger.info(f"User {user_id} - Handling text input. Message: '{message_text}'. Current state: {current_state}")
    
    if current_state == AWAITING_LOGIN_CREDENTIALS:
        from .authentication import handle_auth
        await handle_auth(update, context)
    elif not context.user_data.get('token'):
        logger.warning(f"User {user_id} - Unauthorized text input. Prompting login.")
        await update.message.reply_text("Пожалуйста, авторизуйтесь. Введите email и пароль или нажмите /start.")
        context.user_data['state'] = AWAITING_LOGIN_CREDENTIALS
    elif current_state == AWAITING_RECEIVER:
        await update.message.reply_text("Пожалуйста, выберите руководителя из предложенных кнопок.")
    elif current_state == AWAITING_TIME:
        from .appointments import handle_start_time_input
        await handle_start_time_input(update, context)
    elif current_state == AWAITING_DURATION:
        from .appointments import handle_duration_input
        await handle_duration_input(update, context)
    elif current_state == AWAITING_TOPIC:
        from .appointments import handle_topic_input
        await handle_topic_input(update, context)
    else:
        logger.info(f"User {user_id} - Text input in unhandled state: {current_state}. Defaulting to menu guidance.")
        await update.message.reply_text("Не совсем понял вас. Пожалуйста, используйте меню для навигации.")
        await show_main_menu(update, context)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    role = context.user_data.get('role')
    if not role:
        db = Database()
        user_data = db.get_user_auth(update.effective_user.id)
        if user_data:
            role = user_data.get('role')
            context.user_data['role'] = role
        else:
            msg_target = query.message if query else update.message
            await msg_target.reply_text("Пожалуйста, авторизуйтесь. Нажмите /start")
            return
    
    await show_main_menu(update, context, role)