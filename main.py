import os
import logging
import asyncio
from aiohttp import web
from dotenv import load_dotenv
from db_manager import db_manager
from session_manager import session_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

async def healthcheck(request):
    """Обработчик для healthcheck запросов"""
    return web.Response(text="OK")

async def start_healthcheck_server():
    """Запуск healthcheck сервера"""
    app = web.Application()
    app.router.add_get('/health', healthcheck)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Healthcheck сервер запущен на 0.0.0.0:8080/health")
    return runner

async def main():
    """Основная функция запуска"""
    try:
        # Запускаем healthcheck сервер
        healthcheck_runner = await start_healthcheck_server()
        
        # Инициализируем менеджер сессий
        await session_manager.start()
        
        # Подключаемся к базе данных
        await db_manager.connect()
        
        # Определяем тип бота из переменной окружения
        bot_type = os.getenv('BOT_TYPE', 'web')
        
        if bot_type == 'web':
            # Запускаем только healthcheck сервер
            while True:
                await asyncio.sleep(3600)  # Проверка каждый час
        else:
            # Импортируем и запускаем соответствующий бот
            if bot_type == 'user':
                from user_bot import start_user_bot
                await start_user_bot()
            elif bot_type == 'admin':
                from admin_bot import start_admin_bot
                await start_admin_bot()
            elif bot_type == 'influencer':
                from influencer_bot import start_influencer_bot
                await start_influencer_bot()
            else:
                raise ValueError(f"Неизвестный тип бота: {bot_type}")
    
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        # Закрываем все соединения
        await session_manager.stop()
        await db_manager.close()
        if 'healthcheck_runner' in locals():
            await healthcheck_runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения работы")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
        raise 