import os
import asyncio
import logging
import sys
from typing import Optional
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.exceptions import TelegramAPIError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

def validate_token(token: Optional[str], bot_type: str) -> str:
    """Проверка токена бота"""
    if not token:
        error_msg = f"Токен для {bot_type} бота отсутствует в .env файле"
        logger.error(error_msg)
        raise ValueError(error_msg)
    return token

# Получение и валидация токенов
try:
    USER_BOT_TOKEN = validate_token(os.getenv('USER_BOT_TOKEN'), 'пользовательского')
    ADMIN_BOT_TOKEN = validate_token(os.getenv('ADMIN_BOT_TOKEN'), 'админ')
    INFLUENCER_BOT_TOKEN = validate_token(os.getenv('INFLUENCER_BOT_TOKEN'), 'инфлюенсер')
except ValueError as e:
    logger.error(f"Ошибка валидации токенов: {e}")
    sys.exit(1)

# Получение типа бота
BOT_TYPE = os.getenv('BOT_TYPE', 'all')
if BOT_TYPE not in ['user', 'admin', 'influencer', 'all']:
    logger.error(f"Неверный тип бота: {BOT_TYPE}")
    sys.exit(1)

async def run_bot(bot_type: str, token: str, offset: int):
    """Запуск бота с обработкой ошибок"""
    bot = None
    try:
        bot = Bot(token=token, parse_mode=ParseMode.HTML)
        dp = Dispatcher()
        
        # Проверка доступности бота
        try:
            bot_info = await bot.get_me()
            logger.info(f"Бот {bot_type} (@{bot_info.username}) успешно подключен")
        except TelegramAPIError as e:
            logger.error(f"Ошибка подключения к боту {bot_type}: {e}")
            raise
        
        # Импорт и регистрация хендлеров
        try:
            if bot_type == 'user':
                from user_bot import register_handlers
            elif bot_type == 'admin':
                from admin_bot import register_handlers
            elif bot_type == 'influencer':
                from influencer_bot import register_handlers
                
            register_handlers(dp)
            logger.info(f"Хендлеры для бота {bot_type} успешно зарегистрированы")
        except Exception as e:
            logger.error(f"Ошибка при регистрации хендлеров для бота {bot_type}: {e}")
            raise
        
        logger.info(f"Запуск бота {bot_type}...")
        
        # Настройка параметров polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            polling_timeout=30,
            polling_interval=5.0,
            offset=offset,
            drop_pending_updates=True  # Игнорируем накопившиеся обновления
        )
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота {bot_type}: {e}")
        raise
    finally:
        if bot:
            try:
                await bot.session.close()
                logger.info(f"Сессия бота {bot_type} закрыта")
            except Exception as e:
                logger.error(f"Ошибка при закрытии сессии бота {bot_type}: {e}")

async def start_bots():
    """Запуск всех ботов с обработкой ошибок"""
    try:
        tasks = []
        
        if BOT_TYPE in ['user', 'all']:
            tasks.append(run_bot('user', USER_BOT_TOKEN, 0))
            await asyncio.sleep(10)
            
        if BOT_TYPE in ['admin', 'all']:
            tasks.append(run_bot('admin', ADMIN_BOT_TOKEN, 1000))
            await asyncio.sleep(10)
            
        if BOT_TYPE in ['influencer', 'all']:
            tasks.append(run_bot('influencer', INFLUENCER_BOT_TOKEN, 2000))
            await asyncio.sleep(10)
        
        if not tasks:
            logger.error("Нет ботов для запуска")
            return
        
        # Запускаем все боты
        await asyncio.gather(*tasks)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске ботов: {e}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Запуск приложения...")
        asyncio.run(start_bots())
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1) 