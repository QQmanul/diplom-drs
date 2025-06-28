import logging
import os
from datetime import datetime

def setup_logging():
    try:
        # Получаем абсолютный путь к директории бота
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"Bot directory: {bot_dir}")  # Отладочный вывод

        # Создаем директорию для логов
        log_dir = os.path.join(bot_dir, 'logs')
        print(f"Log directory path: {log_dir}")  # Отладочный вывод
        
        # Создаем директорию, если её нет
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            print(f"Created log directory: {log_dir}")  # Отладочный вывод

        # Формируем имя файла лога с текущей датой
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f'bot_{current_date}.log')
        print(f"Log file path: {log_file}")  # Отладочный вывод

        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', mode='a'),
                logging.StreamHandler()  
            ]
        )

        # Получаем логгер
        logger = logging.getLogger(__name__)
        logger.info("="*50)
        logger.info("Logging initialized")
        logger.info(f"Log file: {log_file}")
        logger.info("="*50)
        
        return logger
    except Exception as e:
        print(f"Error setting up logging: {str(e)}")  # Отладочный вывод
        raise 