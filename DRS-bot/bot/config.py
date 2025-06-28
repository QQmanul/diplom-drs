# bot/config.py

# API Configuration
API_BASE_URL = "http://localhost:5296"

# SignalR Configuration
SIGNALR_HUB_URL = f"{API_BASE_URL}/notification/hub"

# Bot Configuration
BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace with your actual bot token

# Database Configuration
DATABASE_URL = "sqlite:///bot.db"

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s" 