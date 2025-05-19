from aiohttp import web
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def healthcheck(request):
    return web.Response(text="OK", status=200)

async def init_app():
    app = web.Application()
    app.router.add_get('/health', healthcheck)
    return app

if __name__ == '__main__':
    app = init_app()
    web.run_app(app, port=8000) 