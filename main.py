import os
import asyncio
import logging
import multiprocessing
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получение токенов
USER_BOT_TOKEN = os.getenv('USER_BOT_TOKEN')
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
INFLUENCER_BOT_TOKEN = os.getenv('INFLUENCER_BOT_TOKEN')

# Получение типа бота
BOT_TYPE = os.getenv('BOT_TYPE', 'all')

async def run_bot(bot_type: str, token: str):
    try:
        bot = Bot(token=token, parse_mode=ParseMode.HTML)
        dp = Dispatcher()
        
        # Импорт и регистрация хендлеров
        if bot_type == 'user':
            from user_bot import register_handlers
        elif bot_type == 'admin':
            from admin_bot import register_handlers
        elif bot_type == 'influencer':
            from influencer_bot import register_handlers
            
        register_handlers(dp)
        
        logger.info(f"Запуск бота {bot_type}...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота {bot_type}: {e}")
        raise
    finally:
        await bot.session.close()

def start_bot_process(bot_type: str, token: str):
    asyncio.run(run_bot(bot_type, token))

if __name__ == "__main__":
    try:
        processes = []
        
        if BOT_TYPE in ['user', 'all']:
            p = multiprocessing.Process(
                target=start_bot_process,
                args=('user', USER_BOT_TOKEN)
            )
            processes.append(p)
            p.start()
            
        if BOT_TYPE in ['admin', 'all']:
            p = multiprocessing.Process(
                target=start_bot_process,
                args=('admin', ADMIN_BOT_TOKEN)
            )
            processes.append(p)
            p.start()
            
        if BOT_TYPE in ['influencer', 'all']:
            p = multiprocessing.Process(
                target=start_bot_process,
                args=('influencer', INFLUENCER_BOT_TOKEN)
            )
            processes.append(p)
            p.start()
            
        # Ждем завершения всех процессов
        for p in processes:
            p.join()
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        # Завершаем все процессы
        for p in processes:
            if p.is_alive():
                p.terminate() 