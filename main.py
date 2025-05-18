import asyncio
import logging
import sys
import os
from dotenv import load_dotenv
from healthcheck import run_healthcheck_server
import threading

# Загрузка переменных окружения
load_dotenv()

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

# Проверяем какой бот нужно запустить
BOT_TYPE = os.getenv("BOT_TYPE", "all").lower()

# Функция запуска ботов
async def main():
    try:
        # Запускаем healthcheck
        start_healthcheck()
        
        # Импортируем ботов только когда они нужны, чтобы избежать конфликтов
        if BOT_TYPE == "user" or BOT_TYPE == "all":
            from user_bot import dp as user_dp, bot as user_bot
            user_task = asyncio.create_task(user_dp.start_polling(user_bot))
            logger.info("Пользовательский бот запущен!")
        
        if BOT_TYPE == "admin" or BOT_TYPE == "all":
            from admin_bot import dp as admin_dp, bot as admin_bot
            admin_task = asyncio.create_task(admin_dp.start_polling(admin_bot))
            logger.info("Админ бот запущен!")
            
        if BOT_TYPE == "influencer" or BOT_TYPE == "all":
            from influencer_bot import dp as influencer_dp, bot as influencer_bot
            influencer_task = asyncio.create_task(influencer_dp.start_polling(influencer_bot))
            logger.info("Инфлюенсер бот запущен!")
        
        # Если запущены все боты
        if BOT_TYPE == "all":
            await asyncio.gather(user_task, admin_task, influencer_task)
        # Если запущен только пользовательский бот
        elif BOT_TYPE == "user":
            await user_task
        # Если запущен только админский бот
        elif BOT_TYPE == "admin":
            await admin_task
        # Если запущен только инфлюенсер бот
        elif BOT_TYPE == "influencer":
            await influencer_task
        else:
            logger.error(f"Неизвестный тип бота: {BOT_TYPE}. Используйте 'user', 'admin', 'influencer' или 'all'")
    except Exception as e:
        logger.error(f"Ошибка при запуске ботов: {e}")
        raise

if __name__ == "__main__":
    # Запуск через asyncio
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Боты остановлены")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1) 