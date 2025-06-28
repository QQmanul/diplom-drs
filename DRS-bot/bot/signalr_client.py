import aiohttp
import asyncio
import logging
from typing import Optional

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.hub.base_hub_connection import BaseHubConnection
from telegram import Bot

from config import API_BASE_URL # Убедитесь, что этот файл и переменная существуют

logger = logging.getLogger(__name__)

class SignalRClient:
    def __init__(self, bot: Bot, loop: asyncio.AbstractEventLoop):
        self.connections = {}
        self.hub_url = f"{API_BASE_URL}/notificationHub"
        self.bot = bot
        self.loop = loop
        # Словарь для хранения токенов пользователей, чтобы не передавать их постоянно
        self.user_tokens = {}

    async def start_connection(self, telegram_user_id: int, token: str):
        """
        Инициирует соединение SignalR. После успешного подключения 
        автоматически запрашивает историю непрочитанных уведомлений.
        """
        if telegram_user_id in self.connections:
            logger.info(f"Остановка существующего соединения для {telegram_user_id} перед запуском нового.")
            await self.stop_connection(telegram_user_id)
        
        # Сохраняем токен для последующих API-запросов
        self.user_tokens[telegram_user_id] = token

        logger.info(f"Запуск SignalR соединения с {self.hub_url} для пользователя {telegram_user_id}")

        connection = HubConnectionBuilder()\
            .with_url(self.hub_url, options={"access_token_factory": lambda: token})\
            .with_automatic_reconnect({
                "type": "interval",
                "keep_alive_interval": 10,
                "interval": 5,
                "max_attempts": 5
            })\
            .build()
        
        # --- Callbacks ---
        
        def on_notification_callback(message_list):
            """Callback для новых уведомлений, приходящих в реальном времени."""
            try:
                if not message_list: return
                message_content = message_list[0]
                self.loop.call_soon_threadsafe(
                    self._schedule_notification_processing, 
                    telegram_user_id, 
                    message_content
                )
            except Exception as e:
                logger.error(f"Ошибка в callback'е on_notification для {telegram_user_id}: {e}", exc_info=True)

        def on_open_callback():
            """Callback, который вызывается после успешного установления соединения."""
            logger.info(f"SignalR соединение открыто для пользователя {telegram_user_id}")
            self.loop.call_soon_threadsafe(self._schedule_fetch_unread, telegram_user_id)
        
        def on_close_callback():
            """Callback при закрытии соединения."""
            logger.info(f"SignalR соединение закрыто для пользователя {telegram_user_id}")
            if telegram_user_id in self.connections:
                del self.connections[telegram_user_id]
        
        # --- Привязка Callbacks ---
        connection.on("ReceiveNotification", on_notification_callback)
        connection.on_open(on_open_callback)
        connection.on_close(on_close_callback)
        connection.on_error(lambda error: logger.error(f"Ошибка SignalR соединения (callback) для {telegram_user_id}: {error}"))

        try:
            await self.loop.run_in_executor(None, connection.start)
            self.connections[telegram_user_id] = connection
            logger.info(f"SignalR соединение инициировано для пользователя {telegram_user_id}. Ожидание открытия...")
            
        except Exception as e:
            logger.error(f"Ошибка при запуске SignalR соединения для {telegram_user_id}: {e}", exc_info=True)
            if telegram_user_id in self.connections:
                del self.connections[telegram_user_id]

    # --- Вспомогательные методы для планирования задач ---

    def _schedule_notification_processing(self, telegram_user_id: int, message_content: dict):
        """Планирует асинхронную обработку одного уведомления."""
        self.loop.create_task(self.process_and_send_notification(telegram_user_id, message_content))

    def _schedule_fetch_unread(self, telegram_user_id: int):
        """Планирует асинхронную загрузку всех непрочитанных уведомлений."""
        self.loop.create_task(self.fetch_unread_notifications(telegram_user_id))

    # --- Основная логика ---

    async def fetch_unread_notifications(self, telegram_user_id: int):
        """Запрашивает через REST API все непрочитанные уведомления и запускает их обработку."""
        token = self.user_tokens.get(telegram_user_id)
        if not token:
            logger.error(f"Не найден токен для пользователя {telegram_user_id} при попытке загрузить историю.")
            return

        logger.info(f"Начало получения старых непрочитанных уведомлений для {telegram_user_id}")
        try:
            url = f"{API_BASE_URL}/api/Notifications"
            params = {"IsRead": "false", "PageNumber": 1, "PageSize": 50}
            headers = {"Authorization": f"Bearer {token}"}
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        notifications = await response.json()
                        if not notifications:
                            logger.info(f"Нет старых непрочитанных уведомлений для {telegram_user_id}")
                            return
                        
                        logger.info(f"Получено {len(notifications)} старых непрочитанных уведомлений для {telegram_user_id}")
                        await self.bot.send_message(
                            chat_id=telegram_user_id,
                            text=f"📬 У вас есть {len(notifications)} непрочитанных уведомлений. Обрабатываю..."
                        )
                        
                        for notification in notifications:
                            await self.process_and_send_notification(telegram_user_id, notification)
                    else:
                        logger.error(f"Ошибка при получении непрочитанных уведомлений. Статус: {response.status}, Ответ: {await response.text()}")
        except Exception as e:
            logger.error(f"Критическая ошибка в fetch_unread_notifications для {telegram_user_id}: {e}", exc_info=True)

    async def process_and_send_notification(self, telegram_user_id: int, message_content: dict):
        """Форматирует, отправляет уведомление и помечает как прочитанное через API."""
        token = self.user_tokens.get(telegram_user_id)
        if not token:
            logger.error(f"Не найден токен для пользователя {telegram_user_id} при обработке уведомления.")
            return

        try:
            # 1. Форматирование текста
            if isinstance(message_content, dict):
                # ... (ваш код форматирования без изменений) ...
                notification_text = "🔔 <b>Новое уведомление</b>\n\n"
                if 'type' in message_content: notification_text += f"📌 <b>Тип:</b> {message_content['type']}\n"
                if 'message' in message_content: notification_text += f"\n💬 <b>Сообщение:</b>\n{message_content['message']}\n"
                if 'createdAt' in message_content:
                    created_at = message_content['createdAt'].split('.')[0].replace('T', ' ')
                    notification_text += f"\n🕒 <b>Создано:</b> {created_at}\n"
            else:
                notification_text = f"🔔 <b>Новое уведомление</b>\n\n{message_content}"

            # 2. Отправка сообщения в Telegram
            await self.bot.send_message(chat_id=telegram_user_id, text=notification_text, parse_mode='HTML')
            logger.info(f"Уведомление {message_content.get('id')} отправлено пользователю {telegram_user_id}")

            # 3. Пометка как прочитанного через API
            notification_id = message_content.get('id')
            if notification_id:
                success = await self.mark_notification_as_read_api(notification_id, token)
                if success:
                    logger.info(f"Уведомление {notification_id} успешно помечено как прочитанное через API.")
                else:
                    logger.warning(f"Не удалось пометить уведомление {notification_id} как прочитанное через API.")

        except Exception as e:
            logger.error(f"Ошибка в process_and_send_notification для {telegram_user_id}: {e}", exc_info=True)

    async def mark_notification_as_read_api(self, notification_id: str, token: str) -> bool:
        """Помечает уведомление как прочитанное, используя прямой вызов REST API."""
        url = f"{API_BASE_URL}/api/Notifications/{notification_id}/read"
        headers = {"Authorization": f"Bearer {token}"}
        
        logger.info(f"Отправка POST-запроса на {url} для пометки уведомления как прочитанного.")
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(url) as response:
                    if response.status in [200, 204]:  # 204 No Content тоже считается успехом
                        return True
                    else:
                        logger.error(f"API ответил ошибкой {response.status} при пометке уведомления {notification_id} как прочитанного. Ответ: {await response.text()}")
                        return False
        except Exception as e:
            logger.error(f"Ошибка сети при вызове API для пометки уведомления {notification_id}: {e}", exc_info=True)
            return False

    # --- Управление соединениями ---

    async def stop_connection(self, telegram_user_id: int):
        """Останавливает и удаляет соединение для конкретного пользователя."""
        # Удаляем токен вместе с соединением
        if telegram_user_id in self.user_tokens:
            del self.user_tokens[telegram_user_id]
            
        connection = self.connections.pop(telegram_user_id, None)
        if connection:
            logger.info(f"Остановка SignalR соединения для пользователя {telegram_user_id}.")
            try:
                await self.loop.run_in_executor(None, connection.stop)
                logger.info(f"SignalR соединение остановлено для пользователя {telegram_user_id}.")
            except Exception as e:
                logger.error(f"Ошибка при остановке SignalR соединения для {telegram_user_id}: {e}", exc_info=True)
        else:
            logger.info(f"Активное соединение для пользователя {telegram_user_id} не найдено для остановки.")
    
    def get_connection(self, telegram_id: int) -> Optional[BaseHubConnection]:
        """Возвращает активное соединение, если оно существует."""
        return self.connections.get(telegram_id)

    async def stop_all_connections(self):
        """Останавливает все активные соединения SignalR при завершении работы бота."""
        logger.info(f"Остановка всех {len(self.connections)} SignalR соединений.")
        user_ids = list(self.connections.keys())
        tasks = [self.stop_connection(user_id) for user_id in user_ids]
        await asyncio.gather(*tasks)
        logger.info("Все SignalR соединения обработаны для остановки.")