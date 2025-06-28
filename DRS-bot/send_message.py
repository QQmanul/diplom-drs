import requests
import json
import time
from datetime import datetime, timezone, timedelta

# --- Конфигурация ---
API_BASE_URL = "http://localhost:5296"  # ЗАМЕНИТЕ НА URL ВАШЕГО API (проверьте порт!)
TARGET_USER_ID = "a79cdb11-82c4-48bc-b3ec-25047f180bc3"

# Учетные данные пользователя, от имени которого отправляем уведомления (должен иметь права)
# Рекомендуется использовать переменные окружения или более безопасные способы хранения для реальных сценариев
SENDER_EMAIL = "secretary@example.com"  # или admin@example.com
SENDER_PASSWORD = "1234"

# Глобальные переменные для хранения токена и времени его истечения
AUTH_TOKEN = None
TOKEN_EXPIRATION_TIME = None
# Предполагаемое время жизни токена (должно совпадать с настройкой в API, если нет, токен будет обновляться чаще)
# Используется для проактивного обновления токена
TOKEN_DURATION_MINUTES_ESTIMATE = 55 # Чуть меньше, чем фактическое время жизни токена на сервере (например, если там 60)
# --------------------

def get_auth_token():
    """Аутентифицируется и получает JWT токен."""
    global AUTH_TOKEN, TOKEN_EXPIRATION_TIME

    login_url = f"{API_BASE_URL}/api/auth/login"
    payload = {
        "email": SENDER_EMAIL,
        "password": SENDER_PASSWORD
    }
    headers = {
        "Content-Type": "application/json"
    }

    try:
        print(f"Аутентификация пользователя {SENDER_EMAIL}...")
        # Для локальной разработки с самоподписанными SSL-сертификатами может понадобиться verify=False
        # В продакшене verify=True (по умолчанию) и должен быть валидный сертификат
        response = requests.post(login_url, data=json.dumps(payload), headers=headers, verify=False)
        response.raise_for_status()  # Выбросит исключение для HTTP-ошибок (4xx или 5xx)
        
        token_data = response.json()
        AUTH_TOKEN = token_data.get("token")
        
        expiration_str = token_data.get("expiration")
        if AUTH_TOKEN and expiration_str:
            # datetime.fromisoformat хорошо работает с 'Z' и смещениями в современных Python
            if expiration_str.endswith('Z'):
                 TOKEN_EXPIRATION_TIME = datetime.fromisoformat(expiration_str.replace('Z', '+00:00'))
            else:
                # Если нет информации о поясе в строке, fromisoformat создаст наивный datetime.
                # Мы должны предположить, что API возвращает время в UTC, если оно не указано.
                dt_naive = datetime.fromisoformat(expiration_str)
                if dt_naive.tzinfo is None: # Если время наивное
                    TOKEN_EXPIRATION_TIME = dt_naive.replace(tzinfo=timezone.utc)
                else: # Если время уже aware (например, API вернул со смещением)
                    TOKEN_EXPIRATION_TIME = dt_naive.astimezone(timezone.utc) # Приводим к UTC для сравнения

            print(f"Успешная аутентификация. Токен получен. Истекает (UTC): {TOKEN_EXPIRATION_TIME.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            print("Ошибка: Токен или время истечения не найдено в ответе.")
            AUTH_TOKEN = None
            TOKEN_EXPIRATION_TIME = None
        
        return AUTH_TOKEN is not None

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP ошибка при аутентификации: {http_err}")
        if response:
            print(f"Ответ сервера: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"Ошибка запроса при аутентификации: {req_err}")
    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON ответа при аутентификации (ответ сервера: {response.text if 'response' in locals() else 'нет ответа'})")
    except Exception as e:
        print(f"Непредвиденная ошибка при аутентификации: {e}")
    
    AUTH_TOKEN = None
    TOKEN_EXPIRATION_TIME = None
    return False

def send_test_notification():
    """Отправляет тестовое уведомление."""
    global AUTH_TOKEN, TOKEN_EXPIRATION_TIME

    # Проверяем, нужно ли обновить токен
    # Обновляем, если токена нет ИЛИ если предполагаемое время жизни почти истекло
    # datetime.now(timezone.utc) - текущее время в UTC
    if not AUTH_TOKEN or \
       (TOKEN_EXPIRATION_TIME and datetime.now(timezone.utc) >= TOKEN_EXPIRATION_TIME - timedelta(minutes=max(1, TOKEN_DURATION_MINUTES_ESTIMATE // 10))): # Обновляем за 10% до или за 1 мин до
        print("Токен отсутствует или истекает. Попытка повторной аутентификации...")
        if not get_auth_token():
            print("Не удалось получить токен. Пропуск отправки уведомления.")
            return

    notifications_url = f"{API_BASE_URL}/api/notifications"
    payload = {
        "userId": TARGET_USER_ID,
        "message": f"Тестовое уведомление из Python для пользователя {TARGET_USER_ID} в {datetime.now().strftime('%H:%M:%S')}",
        "subject": "Python Test Notification (q.q.)"
        # "appointmentId": None # Можно добавить, если нужно
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }

    try:
        print(f"Отправка тестового уведомления пользователю {TARGET_USER_ID}...")
        response = requests.post(notifications_url, data=json.dumps(payload), headers=headers, verify=False)
        response.raise_for_status()
        print(f"Уведомление успешно отправлено! Статус: {response.status_code}")
        try:
            print(f"Ответ сервера: {response.json()}")
        except json.JSONDecodeError:
            print(f"Ответ сервера (не JSON): {response.text}")

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP ошибка при отправке уведомления: {http_err}")
        if response:
            print(f"Ответ сервера: {response.text}")
        if response and response.status_code == 401: # Не авторизован
            print("Получен статус 401. Возможно, токен стал невалидным. Попытка повторной аутентификации при следующей итерации.")
            AUTH_TOKEN = None # Сбрасываем токен
    except requests.exceptions.RequestException as req_err:
        print(f"Ошибка запроса при отправке уведомления: {req_err}")
    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON ответа при отправке уведомления (ответ сервера: {response.text if 'response' in locals() else 'нет ответа'})")
    except Exception as e:
        print(f"Непредвиденная ошибка при отправке уведомления: {e}")


if __name__ == "__main__":
    print(f"Скрипт запущен. Будет отправлять уведомления каждую минуту на {API_BASE_URL}")
    print(f"Отправитель: {SENDER_EMAIL}, Получатель (тестовый): {TARGET_USER_ID}")
    
    try:
        while True:
            send_test_notification()
            print(f"Ожидание 60 секунд до следующей отправки...\n{'-'*40}")
            time.sleep(60)  # Пауза в 60 секунд (1 минута)
    except KeyboardInterrupt:
        print("\nСкрипт остановлен пользователем.")
    except Exception as e:
        print(f"\nКритическая ошибка в основном цикле: {e}")
    finally:
        print("Завершение работы скрипта.")