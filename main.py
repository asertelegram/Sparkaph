import os
import asyncio
import logging
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

async def start_bots():
    try:
        # Инициализация ботов
        bots = {}
        if BOT_TYPE in ['user', 'all']:
            bots['user'] = Bot(token=USER_BOT_TOKEN, parse_mode=ParseMode.HTML)
        if BOT_TYPE in ['admin', 'all']:
            bots['admin'] = Bot(token=ADMIN_BOT_TOKEN, parse_mode=ParseMode.HTML)
        if BOT_TYPE in ['influencer', 'all']:
            bots['influencer'] = Bot(token=INFLUENCER_BOT_TOKEN, parse_mode=ParseMode.HTML)
        
        # Инициализация диспетчеров
        dispatchers = {}
        for bot_type, bot in bots.items():
            dispatchers[bot_type] = Dispatcher()
        
        # Импорт хендлеров
        if 'user' in bots:
            from user_bot import register_handlers as register_user_handlers
            register_user_handlers(dispatchers['user'])
        
        if 'admin' in bots:
            from admin_bot import register_handlers as register_admin_handlers
            register_admin_handlers(dispatchers['admin'])
        
        if 'influencer' in bots:
            from influencer_bot import register_handlers as register_influencer_handlers
            register_influencer_handlers(dispatchers['influencer'])
        
        # Запуск ботов последовательно
        for bot_type, dp in dispatchers.items():
            logger.info(f"Запуск бота {bot_type}...")
            await dp.start_polling(bots[bot_type])
            await asyncio.sleep(5)  # Увеличиваем задержку между запуском ботов
        
        logger.info(f"Запущены боты: {', '.join(bots.keys())}")
        
        # Держим ботов запущенными
        while True:
            await asyncio.sleep(3600)  # Проверка каждый час
        
    except Exception as e:
        logger.error(f"Ошибка при запуске ботов: {e}")
        raise
    finally:
        # Закрытие ботов
        for bot in bots.values():
            await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(start_bots())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Боты остановлены")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}") 