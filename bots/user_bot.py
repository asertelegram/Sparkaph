import logging
from telegram import Update
from telegram.ext import Application, CommandHandler
from config import USER_BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context):
    """Обработчик команды /start."""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот Sparkaph. Рад тебя видеть!"
    )

async def main():
    """Запуск бота."""
    try:
        application = Application.builder().token(USER_BOT_TOKEN).build()
        application.add_handler(CommandHandler('start', start))
        
        logger.info("Starting User Bot...")
        await application.initialize()
        await application.start()
        await application.run_polling()
        
    except Exception as e:
        logger.error(f"Error in User Bot: {e}")
        raise

if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 