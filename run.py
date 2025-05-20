import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
from config import (
    USER_BOT_TOKEN,
    ADMIN_BOT_TOKEN,
    INFLUENCER_BOT_TOKEN,
    WEBHOOK_URL
)
from database.operations import Database
from utils.states import UserStates, AdminStates, InfluencerStates
import ssl

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()

# Создаем веб-сервер для webhook
app = web.Application()
routes = web.RouteTableDef()

@routes.get('/health')
async def health_check(request):
    return web.Response(text="OK")

@routes.post(f'/webhook/{USER_BOT_TOKEN}')
async def user_bot_webhook(request):
    update = Update.de_json(await request.json(), user_bot)
    await user_bot.process_update(update)
    return web.Response()

@routes.post(f'/webhook/{ADMIN_BOT_TOKEN}')
async def admin_bot_webhook(request):
    update = Update.de_json(await request.json(), admin_bot)
    await admin_bot.process_update(update)
    return web.Response()

@routes.post(f'/webhook/{INFLUENCER_BOT_TOKEN}')
async def influencer_bot_webhook(request):
    update = Update.de_json(await request.json(), influencer_bot)
    await influencer_bot.process_update(update)
    return web.Response()

async def setup_webhook(application: Application, token: str):
    """Настраивает webhook для бота."""
    webhook_url = f"{WEBHOOK_URL}/webhook/{token}"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set for bot {token} at {webhook_url}")

async def start_web_server():
    """Запускает веб-сервер для webhook."""
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Web server started on port 8080")

async def main():
    """Запускает все боты через webhook."""
    try:
        # Инициализируем боты
        global user_bot, admin_bot, influencer_bot
        
        user_bot = Application.builder().token(USER_BOT_TOKEN).build()
        admin_bot = Application.builder().token(ADMIN_BOT_TOKEN).build()
        influencer_bot = Application.builder().token(INFLUENCER_BOT_TOKEN).build()
        
        # Настраиваем webhook для каждого бота
        await setup_webhook(user_bot, USER_BOT_TOKEN)
        await setup_webhook(admin_bot, ADMIN_BOT_TOKEN)
        await setup_webhook(influencer_bot, INFLUENCER_BOT_TOKEN)
        
        # Запускаем веб-сервер
        await start_web_server()
        
        # Держим приложение запущенным
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}") 