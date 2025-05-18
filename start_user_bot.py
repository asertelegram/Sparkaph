import os
import asyncio
import logging
import sys
from dotenv import load_dotenv
from healthcheck import run_healthcheck_server
import threading

# Загрузка переменных окружения
load_dotenv()

# Установка переменной окружения для запуска только пользовательского бота
os.environ["BOT_TYPE"] = "user"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Запуск healthcheck сервера в отдельном потоке
def start_healthcheck():
    t = threading.Thread(target=run_healthcheck_server)
    t.daemon = True
    t.start()
    logger.info("Healthcheck сервер запущен в отдельном потоке")

# Функция запуска бота
async def main():
    try:
        # Запускаем healthcheck
        start_healthcheck()
        
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