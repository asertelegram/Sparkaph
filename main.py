import os
import logging
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiohttp import web
from healthcheck import create_app

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

async def run_bot(bot_type, token):
    bot = Bot(token=token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    try:
        await bot.get_me()
        logger.info(f"{bot_type} бот успешно подключен")
        if bot_type == 'user':
            from user_bot import register_handlers
        elif bot_type == 'admin':
            from admin_bot import register_handlers
        elif bot_type == 'influencer':
            from influencer_bot import register_handlers
        register_handlers(dp)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка {bot_type} бота: {e}")

async def main():
    # Healthcheck сервер
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Healthcheck сервер запущен на 0.0.0.0:8080/health")

    # Боты
    tasks = []
    if os.getenv('USER_BOT_TOKEN'):
        tasks.append(run_bot('user', os.getenv('USER_BOT_TOKEN')))
    if os.getenv('ADMIN_BOT_TOKEN'):
        tasks.append(run_bot('admin', os.getenv('ADMIN_BOT_TOKEN')))
    if os.getenv('INFLUENCER_BOT_TOKEN'):
        tasks.append(run_bot('influencer', os.getenv('INFLUENCER_BOT_TOKEN')))
    if not tasks:
        logger.error("Нет токенов ботов!")
        return

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main()) 