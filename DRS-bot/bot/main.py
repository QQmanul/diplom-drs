import asyncio
import logging
import os
import signal
import sys
from telegram import Update
from telegram.ext import Application
from config import TOKEN
from bot.handlers import setup_handlers
from bot.database import init_db
from bot.logger_config import setup_logging

# Setup logging
logger = setup_logging()

# Global variable for application
app = None

async def cleanup():
    """Cleanup resources on shutdown"""
    if app:
        try:
            await app.stop()
            await app.shutdown()
            logger.info("Application stopped and shut down successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def signal_handler(signum, frame):
    """Signal handler for graceful shutdown"""
    logger.info("Received shutdown signal. Cleaning up resources...")
    asyncio.run(cleanup())
    sys.exit(0)

async def main():
    global app
    try:
        # Initialize database
        init_db()
        logger.info("Database initialized")
        
        # Create application
        app = Application.builder().token(TOKEN).build()
        logger.info("Application created")
        
        # Setup handlers
        setup_handlers(app)
        logger.info("Handlers set up")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers registered")
        
        # Start the bot
        logger.info("Starting bot...")
        await app.initialize()
        await app.start()
        await app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        await cleanup()
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
    finally:
        asyncio.run(cleanup()) 