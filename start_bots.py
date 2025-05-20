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

# Проверка всех необходимых переменных окружения
required_vars = {
    "USER_BOT_TOKEN": os.getenv("USER_BOT_TOKEN"),
    "ADMIN_BOT_TOKEN": os.getenv("ADMIN_BOT_TOKEN"),
    "INFLUENCER_BOT_TOKEN": os.getenv("INFLUENCER_BOT_TOKEN"),
    "ADMIN_ID": os.getenv("ADMIN_ID"),
    "CHANNEL_ID": os.getenv("CHANNEL_ID"),
    "MONGODB_URI": os.getenv("MONGODB_URI"),
    "PORT": os.getenv("PORT", "8080")
}

# Проверка наличия всех переменных
missing_vars = [var for var, value in required_vars.items() if not value]
if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")

logger.info("All environment variables are set")
logger.info(f"PORT: {required_vars['PORT']}")
logger.info(f"ADMIN_ID: {required_vars['ADMIN_ID']}")
logger.info(f"CHANNEL_ID: {required_vars['CHANNEL_ID']}")

# Инициализация ботов
logger.info("Initializing bots...")
user_bot = Bot(token=required_vars["USER_BOT_TOKEN"])
admin_bot = Bot(token=required_vars["ADMIN_BOT_TOKEN"])
influencer_bot = Bot(token=required_vars["INFLUENCER_BOT_TOKEN"])

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
    if str(message.from_user.id) == required_vars["ADMIN_ID"]:
        await message.answer("👋 Привет! Я админ-бот Sparkaph.")
    else:
        await message.answer("⛔ У вас нет доступа к админ-боту.")

@admin_dp.message()
async def admin_echo(message: types.Message):
    if str(message.from_user.id) == required_vars["ADMIN_ID"]:
        logger.info(f"Admin bot received message: {message.text} from admin {message.from_user.id}")
        await message.answer(f"Админ, вы написали: {message.text}")
    else:
        logger.warning(f"Unauthorized access attempt to admin bot from user {message.from_user.id}")
        await message.answer("⛔ У вас нет доступа к админ-боту.")

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
        port = int(required_vars["PORT"])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"Web server started on port {port}")
        
        # Запуск ботов с задержкой
        logger.info("Starting bots...")
        logger.info(f"User bot token: {required_vars['USER_BOT_TOKEN'][:5]}...")
        logger.info(f"Admin bot token: {required_vars['ADMIN_BOT_TOKEN'][:5]}...")
        logger.info(f"Influencer bot token: {required_vars['INFLUENCER_BOT_TOKEN'][:5]}...")
        
        # Запускаем ботов последовательно с задержкой
        await user_dp.start_polling(user_bot)
        await asyncio.sleep(2)  # Ждем 2 секунды
        await admin_dp.start_polling(admin_bot)
        await asyncio.sleep(2)  # Ждем 2 секунды
        await influencer_dp.start_polling(influencer_bot)
        
        # Держим ботов запущенными
        while True:
            await asyncio.sleep(3600)  # Проверяем каждый час
            
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