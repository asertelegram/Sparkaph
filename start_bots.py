import asyncio
import os
from aiogram import Bot, Dispatcher
from aiohttp import web
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Инициализация ботов
user_bot = Bot(token=os.getenv("USER_BOT_TOKEN"))
admin_bot = Bot(token=os.getenv("ADMIN_BOT_TOKEN"))
influencer_bot = Bot(token=os.getenv("INFLUENCER_BOT_TOKEN"))

# Инициализация диспетчеров
user_dp = Dispatcher()
admin_dp = Dispatcher()
influencer_dp = Dispatcher()

# Healthcheck endpoint
async def healthcheck(request):
    return web.Response(text="OK")

# Создание веб-приложения
app = web.Application()
app.router.add_get('/health', healthcheck)

async def start_bots():
    # Запуск веб-сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 8080)))
    await site.start()
    
    # Запуск ботов
    await asyncio.gather(
        user_dp.start_polling(user_bot),
        admin_dp.start_polling(admin_bot),
        influencer_dp.start_polling(influencer_bot)
    )

if __name__ == '__main__':
    asyncio.run(start_bots()) 