import os
import sys
import logging
import multiprocessing
from typing import Optional
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from healthcheck import start_healthcheck

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

async def run_bot(bot_type: str, token: str):
    """Запуск бота в отдельном процессе"""
    try:
        bot = Bot(token=token, parse_mode=ParseMode.HTML)
        dp = Dispatcher()
        
        # Проверка доступности бота
        try:
            bot_info = await bot.get_me()
            logger.info(f"Бот {bot_type} (@{bot_info.username}) успешно подключен")
        except TelegramAPIError as e:
            logger.error(f"Ошибка подключения к боту {bot_type}: {e}")
            return
        
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
            return
        
        logger.info(f"Запуск бота {bot_type}...")
        
        # Настройка параметров polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            polling_timeout=30,
            polling_interval=5.0,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота {bot_type}: {e}")
    finally:
        if 'bot' in locals():
            try:
                await bot.session.close()
                logger.info(f"Сессия бота {bot_type} закрыта")
            except Exception as e:
                logger.error(f"Ошибка при закрытии сессии бота {bot_type}: {e}")

def run_bot_process(bot_type: str, token: str):
    """Запуск бота в отдельном процессе"""
    import asyncio
    asyncio.run(run_bot(bot_type, token))

def main():
    """Основная функция запуска ботов"""
    try:
        # Запускаем healthcheck сервер
        healthcheck_thread = start_healthcheck()
        if not healthcheck_thread:
            logger.error("Не удалось запустить healthcheck сервер")
            sys.exit(1)
        logger.info("Healthcheck сервер успешно запущен")
        
        # Получение и валидация токенов
        USER_BOT_TOKEN = validate_token(os.getenv('USER_BOT_TOKEN'), 'пользовательского')
        ADMIN_BOT_TOKEN = validate_token(os.getenv('ADMIN_BOT_TOKEN'), 'админ')
        INFLUENCER_BOT_TOKEN = validate_token(os.getenv('INFLUENCER_BOT_TOKEN'), 'инфлюенсер')
        
        # Получение типа бота
        BOT_TYPE = os.getenv('BOT_TYPE', 'all')
        if BOT_TYPE not in ['user', 'admin', 'influencer', 'all']:
            logger.error(f"Неверный тип бота: {BOT_TYPE}")
            sys.exit(1)
        
        # Создаем процессы для ботов
        processes = []
        
        if BOT_TYPE in ['user', 'all']:
            p = multiprocessing.Process(
                target=run_bot_process,
                args=('user', USER_BOT_TOKEN),
                name='UserBot'
            )
            processes.append(p)
        
        if BOT_TYPE in ['admin', 'all']:
            p = multiprocessing.Process(
                target=run_bot_process,
                args=('admin', ADMIN_BOT_TOKEN),
                name='AdminBot'
            )
            processes.append(p)
        
        if BOT_TYPE in ['influencer', 'all']:
            p = multiprocessing.Process(
                target=run_bot_process,
                args=('influencer', INFLUENCER_BOT_TOKEN),
                name='InfluencerBot'
            )
            processes.append(p)
        
        if not processes:
            logger.error("Нет ботов для запуска")
            return
        
        # Запускаем все процессы
        for p in processes:
            p.start()
            logger.info(f"Запущен процесс {p.name}")
        
        # Ждем завершения всех процессов
        for p in processes:
            p.join()
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Устанавливаем метод запуска для Windows
    if sys.platform == 'win32':
        multiprocessing.set_start_method('spawn')
    
    main() 