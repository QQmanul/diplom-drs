import logging
import asyncio
from telegram.ext import Application
from config import BOT_TOKEN
from bot.handlers import setup_handlers
from bot.signalr_client import SignalRClient
from bot.logger_config import setup_logging

# Setup logging
logger = setup_logging()

async def main():
    app = None
    try:
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()
        
        loop = asyncio.get_running_loop()
        # Initialize SignalR client
        app.bot_data['signalr_client'] = SignalRClient(app.bot, loop)
        
        # Setup handlers
        setup_handlers(app)
        
        # Start the bot
        logger.info("Starting bot...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logger.info("Bot started successfully")
        
        # Keep the bot running
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        if app:
            try:
                await app.stop()
                logger.info("Bot stopped successfully")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Critical error: {e}")
