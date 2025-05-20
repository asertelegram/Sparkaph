import asyncio
import logging
from bots.user_bot import main as user_bot_main
from bots.admin_bot import main as admin_bot_main
from bots.influencer_bot import main as influencer_bot_main

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_all_bots():
    """Запускает все боты последовательно."""
    try:
        logger.info("Starting bots...")
        
        # Запускаем боты последовательно
        await user_bot_main()
        await asyncio.sleep(2)  # Ждем 2 секунды
        await admin_bot_main()
        await asyncio.sleep(2)  # Ждем 2 секунды
        await influencer_bot_main()
        
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