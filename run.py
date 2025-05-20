import asyncio
import logging
from aiohttp import web
from bots.user_bot import main as user_bot_main
from bots.admin_bot import main as admin_bot_main
from bots.influencer_bot import main as influencer_bot_main

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем веб-сервер для health check
async def health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Web server started on port 8080")

async def run_all_bots():
    """Запускает все боты асинхронно."""
    try:
        # Запускаем веб-сервер
        await start_web_server()
        
        # Запускаем боты с задержкой между ними
        logger.info("Starting bots...")
        
        # Запускаем боты последовательно с небольшой задержкой
        await user_bot_main()
        await asyncio.sleep(2)  # Ждем 2 секунды
        await admin_bot_main()
        await asyncio.sleep(2)  # Ждем 2 секунды
        await influencer_bot_main()
        
        # Держим ботов запущенными
        while True:
            await asyncio.sleep(3600)  # Проверяем каждый час
            
    except Exception as e:
        logger.error(f"Error running bots: {e}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(run_all_bots())
    except KeyboardInterrupt:
        logger.info("Bots stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}") 