from aiohttp import web
import logging
import asyncio
import threading
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальная переменная для отслеживания состояния
is_healthy = True

async def healthcheck(request):
    global is_healthy
    try:
        if is_healthy:
            return web.Response(text="OK", status=200)
        else:
            return web.Response(text="Not Healthy", status=503)
    except Exception as e:
        logger.error(f"Ошибка в healthcheck: {e}")
        return web.Response(text="Error", status=500)

async def init_app():
    app = web.Application()
    app.router.add_get('/health', healthcheck)
    return app

async def run_server():
    """Запуск сервера в асинхронном режиме"""
    try:
        app = await init_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        logger.info("Healthcheck сервер запущен на порту 8080")
        
        # Держим сервер запущенным
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Ошибка запуска healthcheck сервера: {e}")
        global is_healthy
        is_healthy = False
        raise

def run_healthcheck():
    """Запуск healthcheck сервера в отдельном потоке"""
    try:
        asyncio.run(run_server())
    except Exception as e:
        logger.error(f"Ошибка в процессе healthcheck: {e}")
        global is_healthy
        is_healthy = False

def start_healthcheck():
    """Запуск healthcheck сервера в фоновом режиме"""
    thread = threading.Thread(target=run_healthcheck, daemon=True)
    thread.start()
    
    # Ждем запуска сервера
    time.sleep(2)
    
    if thread.is_alive():
        logger.info("Healthcheck сервер успешно запущен в отдельном потоке")
        return thread
    else:
        logger.error("Не удалось запустить healthcheck сервер")
        return None

if __name__ == '__main__':
    thread = start_healthcheck()
    if thread:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения") 