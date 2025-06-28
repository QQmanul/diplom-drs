# This file makes the handlers directory a Python package
# Import commonly used handlers for convenience
from bot.handlers.authentication import start, handle_auth, logout
from bot.handlers.appointments import (
    show_appointments, create_appointment, handle_receiver_selection,
    handle_start_time_input, handle_duration_input, handle_topic_input,
    manage_appointments, handle_appointment_action
)
from bot.handlers.profile import handle_profile, handle_notifications
from bot.handlers.queue import show_queue
from bot.handlers.common import handle_text_input, handle_main_menu
from bot.handlers.main_handler_setup import setup_handlers 