import asyncio
import logging
from server import init_server, shutdown_server

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
        # Инициализация сервера
        server = await init_server()
        logger.info("Server started successfully")
        
        # Получаем статус системы
        status = await server.get_system_status()
        logger.info(f"System status: {status}")
        
        # Держим сервер запущенным
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        # Корректное завершение работы
        await shutdown_server()
        logger.info("Server stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user") 