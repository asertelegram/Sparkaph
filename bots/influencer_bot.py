import asyncio
from telegram import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.ext import ConversationHandler

async def main():
    """Запуск бота."""
    application = Application.builder().token(INFLUENCER_BOT_TOKEN).build()
    
    # Создаем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            InfluencerStates.MAIN_MENU: [
                CallbackQueryHandler(handle_influencer_menu)
            ],
            InfluencerStates.CREATING_CHALLENGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_challenge_creation)
            ],
            InfluencerStates.VIEWING_STATS: [
                CallbackQueryHandler(handle_stats)
            ]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    
    # Запускаем бота
    await application.initialize()
    await application.start()
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main()) 