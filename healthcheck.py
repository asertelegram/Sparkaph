from aiohttp import web
import logging
import asyncio
import threading

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def healthcheck(request):
    try:
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"Ошибка в healthcheck: {e}")
        return web.Response(text="Error", status=500)

async def init_app():
    app = web.Application()
    app.router.add_get('/health', healthcheck)
    return app

def run_healthcheck():
    """Запуск healthcheck сервера в отдельном потоке"""
    try:
        app = init_app()
        web.run_app(app, port=8080, host='0.0.0.0')
    except Exception as e:
        logger.error(f"Ошибка запуска healthcheck сервера: {e}")

def start_healthcheck():
    """Запуск healthcheck сервера в фоновом режиме"""
    thread = threading.Thread(target=run_healthcheck, daemon=True)
    thread.start()
    logger.info("Healthcheck сервер запущен в отдельном потоке")
    return thread

if __name__ == '__main__':
    start_healthcheck()
    # Держим основной поток активным
    try:
        while True:
            asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения") 