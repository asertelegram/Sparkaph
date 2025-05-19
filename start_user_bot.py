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

# Установка переменной окружения для запуска только пользовательского бота
os.environ["BOT_TYPE"] = "user"
os.environ["PORT"] = "8081"  # Уникальный порт для user bot

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
async def start_healthcheck():
    port = int(os.environ.get('PORT', 8081))
    if not is_port_in_use(port):
        await run_healthcheck_server()
        logger.info(f"Healthcheck сервер запущен на порту {port}")
    else:
        logger.warning(f"Порт {port} занят, healthcheck сервер не запущен")

# Функция запуска бота
async def main():
    try:
        # Запускаем healthcheck
        await start_healthcheck()
        
        # Импортируем только пользовательского бота
        from user_bot import dp as user_dp, bot as user_bot
        
        logger.info("Запуск пользовательского бота...")
        
        # Запускаем пользовательского бота
        await user_dp.start_polling(user_bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске пользовательского бота: {e}")
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