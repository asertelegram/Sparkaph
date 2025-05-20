import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from dotenv import load_dotenv
from PIL import Image
import pytz

load_dotenv()

BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("ADMIN_BOT_TOKEN отсутствует в .env файле")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Healthcheck
async def healthcheck(request):
    return web.Response(text="OK")

async def start_healthcheck():
    app = web.Application()
    app.router.add_get('/health', healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Admin-бот запущен и работает!")

@dp.message()
async def echo(message: types.Message):
    await message.answer(message.text)

async def main():
    await start_healthcheck()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 