import logging
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Импортируем хендлеры из соответствующих модулей
from .authentication import start, handle_auth, logout
from .appointments import (
    show_appointments, create_appointment, handle_receiver_selection,
    manage_appointments, handle_appointment_action
    # Текстовые обработчики для состояний (handle_start_time_input и т.д.) вызываются из handle_text_input
)
from .profile import handle_profile, handle_notifications
from .queue import show_queue, update_queue_item_status
from .common import handle_text_input, handle_main_menu

logger = logging.getLogger(__name__)

def setup_handlers(app):
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logout", logout)) # Команда /logout
    
    # CallbackQueryHandlers
    app.add_handler(CallbackQueryHandler(show_appointments, pattern='my_appointments'))
    app.add_handler(CallbackQueryHandler(create_appointment, pattern='create_appointment'))
    app.add_handler(CallbackQueryHandler(show_queue, pattern='show_queue'))
    app.add_handler(CallbackQueryHandler(update_queue_item_status, pattern=r'^queue_status:'))
    app.add_handler(CallbackQueryHandler(handle_receiver_selection, pattern=r'^select_receiver_'))
    app.add_handler(CallbackQueryHandler(handle_profile, pattern='profile'))
    app.add_handler(CallbackQueryHandler(handle_notifications, pattern='notifications')) 
    app.add_handler(CallbackQueryHandler(handle_main_menu, pattern='main_menu')) 
    app.add_handler(CallbackQueryHandler(logout, pattern='logout')) # Кнопка "Выйти"
    
    app.add_handler(CallbackQueryHandler(manage_appointments, pattern='manage_appointments'))
    app.add_handler(CallbackQueryHandler(handle_appointment_action, pattern=r'^app_action:'))

    # Text input handler (должен быть одним из последних или с правильным group)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    logger.info("All bot handlers set up from modular files.")