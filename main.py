import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

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

async def run_bot(bot_type: str, token: str, offset: int):
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
        
        # Настройка параметров polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            polling_timeout=30,
            polling_interval=5.0,  # Увеличенный интервал
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота {bot_type}: {e}")
        raise
    finally:
        await bot.session.close()

async def start_bots():
    try:
        tasks = []
        
        if BOT_TYPE in ['user', 'all']:
            tasks.append(run_bot('user', USER_BOT_TOKEN, 0))
            await asyncio.sleep(10)  # Увеличенная задержка
            
        if BOT_TYPE in ['admin', 'all']:
            tasks.append(run_bot('admin', ADMIN_BOT_TOKEN, 1000))
            await asyncio.sleep(10)
            
        if BOT_TYPE in ['influencer', 'all']:
            tasks.append(run_bot('influencer', INFLUENCER_BOT_TOKEN, 2000))
            await asyncio.sleep(10)
        
        # Запускаем все боты
        await asyncio.gather(*tasks)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске ботов: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(start_bots())
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}") 