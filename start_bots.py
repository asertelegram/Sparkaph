import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Проверка токенов
USER_BOT_TOKEN = os.getenv("USER_BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
INFLUENCER_BOT_TOKEN = os.getenv("INFLUENCER_BOT_TOKEN")

if not all([USER_BOT_TOKEN, ADMIN_BOT_TOKEN, INFLUENCER_BOT_TOKEN]):
    logger.error("Missing bot tokens in environment variables!")
    raise ValueError("Missing bot tokens in environment variables!")

logger.info("Initializing bots...")
# Инициализация ботов
user_bot = Bot(token=USER_BOT_TOKEN)
admin_bot = Bot(token=ADMIN_BOT_TOKEN)
influencer_bot = Bot(token=INFLUENCER_BOT_TOKEN)

# Инициализация диспетчеров
user_dp = Dispatcher()
admin_dp = Dispatcher()
influencer_dp = Dispatcher()

# Обработчики для user_bot
@user_dp.message(Command("start"))
async def user_start(message: types.Message):
    logger.info(f"User bot received /start command from user {message.from_user.id}")
    await message.answer("👋 Привет! Я бот для пользователей Sparkaph.")

@user_dp.message()
async def user_echo(message: types.Message):
    logger.info(f"User bot received message: {message.text} from user {message.from_user.id}")
    await message.answer(f"Вы написали: {message.text}")

# Обработчики для admin_bot
@admin_dp.message(Command("start"))
async def admin_start(message: types.Message):
    logger.info(f"Admin bot received /start command from user {message.from_user.id}")
    await message.answer("👋 Привет! Я админ-бот Sparkaph.")

@admin_dp.message()
async def admin_echo(message: types.Message):
    logger.info(f"Admin bot received message: {message.text} from user {message.from_user.id}")
    await message.answer(f"Админ, вы написали: {message.text}")

# Обработчики для influencer_bot
@influencer_dp.message(Command("start"))
async def influencer_start(message: types.Message):
    logger.info(f"Influencer bot received /start command from user {message.from_user.id}")
    await message.answer("👋 Привет! Я бот для инфлюенсеров Sparkaph.")

@influencer_dp.message()
async def influencer_echo(message: types.Message):
    logger.info(f"Influencer bot received message: {message.text} from user {message.from_user.id}")
    await message.answer(f"Инфлюенсер, вы написали: {message.text}")

# Healthcheck endpoint
async def healthcheck(request):
    return web.Response(text="OK")

# Создание веб-приложения
app = web.Application()
app.router.add_get('/health', healthcheck)

async def start_bots():
    try:
        # Запуск веб-сервера
        port = int(os.getenv('PORT', 8080))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"Web server started on port {port}")
        
        # Запуск ботов
        logger.info("Starting bots...")
        logger.info(f"User bot token: {USER_BOT_TOKEN[:5]}...")
        logger.info(f"Admin bot token: {ADMIN_BOT_TOKEN[:5]}...")
        logger.info(f"Influencer bot token: {INFLUENCER_BOT_TOKEN[:5]}...")
        
        await asyncio.gather(
            user_dp.start_polling(user_bot),
            admin_dp.start_polling(admin_bot),
            influencer_dp.start_polling(influencer_bot)
        )
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(start_bots())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application stopped due to error: {e}") 