import os
import asyncio
import logging
import sys
import socket
from dotenv import load_dotenv
from healthcheck import run_healthcheck_server
import threading

# Загрузка переменных окружения
load_dotenv()

# Установка переменной окружения для запуска только админского бота
os.environ["BOT_TYPE"] = "admin"
os.environ["PORT"] = "8082"  # Уникальный порт для admin bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Запуск healthcheck сервера в отдельном потоке
def start_healthcheck():
    port = int(os.environ.get('PORT', 8082))
    if not is_port_in_use(port):
    t = threading.Thread(target=run_healthcheck_server)
    t.daemon = True
    t.start()
        logger.info(f"Healthcheck сервер запущен на порту {port}")
    else:
        logger.warning(f"Порт {port} занят, healthcheck сервер не запущен")

# Функция запуска бота
async def main():
    try:
        # Запускаем healthcheck
        start_healthcheck()
        
        # Импортируем только админского бота
        from admin_bot import dp as admin_dp, bot as admin_bot
        
        logger.info("Запуск админского бота...")
        
        # Запускаем админского бота
        await admin_dp.start_polling(admin_bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске админского бота: {e}")
        raise

if __name__ == "__main__":
    # Запуск через asyncio
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1) 