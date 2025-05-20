import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
from config import ADMIN_BOT_TOKEN, ADMIN_ID
from database.operations import Database
from utils.keyboards import (
    get_admin_menu_keyboard,
    get_moderation_keyboard,
    get_confirmation_keyboard
)
from utils.states import AdminStates
from utils.helpers import format_challenge_info, format_challenge_stats

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()

async def start(update: Update, context):
    """Обработчик команды /start."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к админ-панели.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Добро пожаловать в админ-панель!",
        reply_markup=get_admin_menu_keyboard()
    )
    return AdminStates.MAIN_MENU

async def handle_admin_menu(update: Update, context):
    """Обработчик админ-меню."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "moderate_videos":
        submissions = await db.get_pending_submissions()
        if submissions:
            submission = submissions[0]
            await query.message.edit_text(
                f"Видео на модерацию:\n\n"
                f"От пользователя: {submission['user_id']}\n"
                f"Челлендж: {submission['challenge_id']}\n"
                f"Отправлено: {submission['submitted_at']}",
                reply_markup=get_moderation_keyboard(submission['submission_id'])
            )
            return AdminStates.MODERATING_VIDEOS
        else:
            await query.message.edit_text(
                "Нет видео на модерацию.",
                reply_markup=get_admin_menu_keyboard()
            )
    
    elif query.data == "add_challenge":
        await query.message.edit_text(
            "Создание нового челленджа:\n\n"
            "1. Отправьте название челленджа:",
            reply_markup=get_admin_menu_keyboard()
        )
        return AdminStates.ADDING_CHALLENGE
    
    elif query.data == "manage_influencers":
        await query.message.edit_text(
            "Управление блогерами:\n\n"
            "1. Добавить блогера\n"
            "2. Редактировать блогера\n"
            "3. Удалить блогера",
            reply_markup=get_admin_menu_keyboard()
        )
        return AdminStates.MANAGING_INFLUENCERS
    
    elif query.data == "admin_stats":
        await query.message.edit_text(
            "Статистика:\n\n"
            "1. Общая статистика\n"
            "2. По челленджам\n"
            "3. По блогерам\n"
            "4. По виральности",
            reply_markup=get_admin_menu_keyboard()
        )
        return AdminStates.VIEWING_STATS

async def handle_moderation(update: Update, context):
    """Обработчик модерации видео."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("approve_"):
        submission_id = int(query.data.split("_")[1])
        await db.update_submission_status(
            submission_id,
            "approved",
            moderator_id=ADMIN_ID
        )
        await query.message.edit_text(
            "Видео одобрено!",
            reply_markup=get_admin_menu_keyboard()
        )
        return AdminStates.MAIN_MENU
    
    elif query.data.startswith("reject_"):
        submission_id = int(query.data.split("_")[1])
        await query.message.edit_text(
            "Укажите причину отказа:",
            reply_markup=get_admin_menu_keyboard()
        )
        context.user_data['rejecting_submission'] = submission_id
        return AdminStates.REJECTING_VIDEO
    
    elif query.data.startswith("skip_"):
        submissions = await db.get_pending_submissions()
        if submissions:
            submission = submissions[0]
            await query.message.edit_text(
                f"Видео на модерацию:\n\n"
                f"От пользователя: {submission['user_id']}\n"
                f"Челлендж: {submission['challenge_id']}\n"
                f"Отправлено: {submission['submitted_at']}",
                reply_markup=get_moderation_keyboard(submission['submission_id'])
            )
        else:
            await query.message.edit_text(
                "Нет видео на модерацию.",
                reply_markup=get_admin_menu_keyboard()
            )
            return AdminStates.MAIN_MENU

async def handle_rejection_reason(update: Update, context):
    """Обработчик ввода причины отказа."""
    submission_id = context.user_data.get('rejecting_submission')
    if not submission_id:
        await update.message.reply_text(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=get_admin_menu_keyboard()
        )
        return AdminStates.MAIN_MENU
    
    reason = update.message.text
    await db.update_submission_status(
        submission_id,
        "rejected",
        moderator_id=ADMIN_ID,
        rejection_reason=reason
    )
    
    await update.message.reply_text(
        "Видео отклонено!",
        reply_markup=get_admin_menu_keyboard()
    )
    return AdminStates.MAIN_MENU

async def handle_challenge_creation(update: Update, context):
    """Обработчик создания челленджа."""
    if 'challenge_data' not in context.user_data:
        context.user_data['challenge_data'] = {}
    
    if 'step' not in context.user_data:
        context.user_data['step'] = 'title'
    
    if context.user_data['step'] == 'title':
        context.user_data['challenge_data']['title'] = update.message.text
        await update.message.reply_text(
            "Отправьте описание челленджа:",
            reply_markup=get_admin_menu_keyboard()
        )
        context.user_data['step'] = 'description'
    
    elif context.user_data['step'] == 'description':
        context.user_data['challenge_data']['description'] = update.message.text
        await update.message.reply_text(
            "Отправьте категорию челленджа:",
            reply_markup=get_admin_menu_keyboard()
        )
        context.user_data['step'] = 'category'
    
    elif context.user_data['step'] == 'category':
        context.user_data['challenge_data']['category'] = update.message.text
        await update.message.reply_text(
            "Отправьте уровень сложности (1-5):",
            reply_markup=get_admin_menu_keyboard()
        )
        context.user_data['step'] = 'difficulty'
    
    elif context.user_data['step'] == 'difficulty':
        try:
            difficulty = int(update.message.text)
            if 1 <= difficulty <= 5:
                context.user_data['challenge_data']['difficulty'] = difficulty
                challenge_data = context.user_data['challenge_data']
                
                # Создаем челлендж
                await db.create_challenge({
                    "title": challenge_data['title'],
                    "description": challenge_data['description'],
                    "category": challenge_data['category'],
                    "difficulty": challenge_data['difficulty'],
                    "created_by": ADMIN_ID
                })
                
                await update.message.reply_text(
                    "Челлендж успешно создан!",
                    reply_markup=get_admin_menu_keyboard()
                )
                return AdminStates.MAIN_MENU
            else:
                await update.message.reply_text(
                    "Сложность должна быть от 1 до 5. Попробуйте снова:",
                    reply_markup=get_admin_menu_keyboard()
                )
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введите число от 1 до 5:",
                reply_markup=get_admin_menu_keyboard()
            )

def main():
    """Запуск бота."""
    application = Application.builder().token(ADMIN_BOT_TOKEN).build()
    
    # Создаем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            AdminStates.MAIN_MENU: [
                CallbackQueryHandler(handle_admin_menu)
            ],
            AdminStates.MODERATING_VIDEOS: [
                CallbackQueryHandler(handle_moderation)
            ],
            AdminStates.REJECTING_VIDEO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rejection_reason)
            ],
            AdminStates.ADDING_CHALLENGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_challenge_creation)
            ]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main() 