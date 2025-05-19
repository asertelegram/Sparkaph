import asyncio
import logging
import os
from dotenv import load_dotenv
from healthcheck import run_healthcheck_server
import threading

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start_bot(bot_type):
    try:
        if bot_type == "admin":
            from admin_bot import dp as admin_dp, bot as admin_bot
            logger.info("Запуск админ бота...")
            await admin_dp.start_polling(admin_bot)
        elif bot_type == "user":
            from user_bot import dp as user_dp, bot as user_bot
            logger.info("Запуск пользовательского бота...")
            await user_dp.start_polling(user_bot)
        elif bot_type == "influencer":
            from influencer_bot import dp as inf_dp, bot as inf_bot
            logger.info("Запуск инфлюенсер бота...")
            await inf_dp.start_polling(inf_bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске {bot_type} бота: {e}")
        raise

async def main():
    try:
        # Запускаем healthcheck сервер
        healthcheck_thread = threading.Thread(target=lambda: asyncio.run(run_healthcheck_server()))
        healthcheck_thread.start()
        logger.info("Healthcheck сервер запущен в отдельном потоке")
        
        # Запускаем ботов последовательно
        bots = ["admin", "user", "influencer"]
        for bot_type in bots:
            await start_bot(bot_type)
            # Даем время на инициализацию
            await asyncio.sleep(2)
            
    except Exception as e:
        logger.error(f"Ошибка в главном цикле: {e}")
    finally:
        logger.info("Сервер остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен пользователем") 