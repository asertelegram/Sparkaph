from aiohttp import web
import os

async def healthcheck(request):
    return web.Response(text="OK", status=200)

def create_app():
    app = web.Application()
    app.router.add_get('/health', healthcheck)
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 8080))
    web.run_app(app, port=port, host='0.0.0.0') 