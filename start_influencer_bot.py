import asyncio
import logging
import os
from influencer_bot import main

# Установка порта для healthcheck
os.environ["PORT"] = "8083"  # Уникальный порт для influencer bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Запуск бота для инфлюенсеров...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}") 