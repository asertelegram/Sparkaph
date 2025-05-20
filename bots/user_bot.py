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
from config import USER_BOT_TOKEN, WELCOME_MESSAGE
from database.operations import Database
from utils.keyboards import (
    get_main_menu_keyboard,
    get_onboarding_keyboard,
    get_language_keyboard,
    get_categories_keyboard,
    get_challenge_actions_keyboard,
    get_leaderboard_period_keyboard
)
from utils.states import UserStates
from utils.helpers import (
    format_challenge_info,
    format_user_stats,
    format_leaderboard_entry,
    get_random_challenge,
    validate_video_duration
)

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
    user = update.effective_user
    user_data = await db.get_user(user.id)
    
    if not user_data:
        # Новый пользователь
        await update.message.reply_text(
            WELCOME_MESSAGE,
            reply_markup=get_onboarding_keyboard()
        )
        return UserStates.ONBOARDING
    else:
        # Существующий пользователь
        await update.message.reply_text(
            f"С возвращением, {user.first_name}!",
            reply_markup=get_main_menu_keyboard()
        )
        return UserStates.MAIN_MENU

async def handle_onboarding(update: Update, context):
    """Обработчик онбординга."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "what_is_this":
        await query.message.edit_text(
            "Sparkaph - это платформа для челленджей, где вы можете:\n"
            "🎯 Участвовать в различных челленджах\n"
            "📱 Снимать и отправлять видео\n"
            "🏆 Получать награды и бейджи\n"
            "👥 Соревноваться с другими участниками",
            reply_markup=get_onboarding_keyboard()
        )
    elif query.data == "how_to_participate":
        await query.message.edit_text(
            "Как участвовать:\n\n"
            "1. Выберите интересный челлендж\n"
            "2. Снимите видео выполнения\n"
            "3. Отправьте видео в бота\n"
            "4. Получите обратную связь\n"
            "5. Зарабатывайте награды!",
            reply_markup=get_onboarding_keyboard()
        )
    elif query.data == "view_examples":
        await query.message.edit_text(
            "Посмотрите примеры в нашем канале: @SparkaphChannel",
            reply_markup=get_language_keyboard()
        )
        return UserStates.LANGUAGE_SELECTION

async def handle_language_selection(update: Update, context):
    """Обработчик выбора языка."""
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split('_')[1]
    user = update.effective_user
    
    # Создаем нового пользователя
    await db.create_user({
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": lang,
        "referral_code": generate_referral_code()
    })
    
    await query.message.edit_text(
        "Отлично! Теперь вы можете начать участвовать в челленджах.",
        reply_markup=get_main_menu_keyboard()
    )
    return UserStates.MAIN_MENU

async def handle_main_menu(update: Update, context):
    """Обработчик главного меню."""
    text = update.message.text
    
    if text == "🎯 Челленджи":
        await update.message.reply_text(
            "Выберите категорию:",
            reply_markup=get_categories_keyboard()
        )
        return UserStates.VIEWING_CHALLENGES
    
    elif text == "📱 Мои челленджи":
        user = update.effective_user
        stats = await db.get_user_stats(user.id)
        await update.message.reply_text(
            format_user_stats(stats),
            reply_markup=get_main_menu_keyboard()
        )
    
    elif text == "📊 Лидерборд":
        await update.message.reply_text(
            "Выберите период:",
            reply_markup=get_leaderboard_period_keyboard()
        )
    
    elif text == "🎲 Рандом челлендж":
        challenges = await db.get_active_challenges()
        challenge = get_random_challenge(challenges)
        if challenge:
            await update.message.reply_text(
                format_challenge_info(challenge),
                reply_markup=get_challenge_actions_keyboard(challenge['challenge_id'])
            )
        else:
            await update.message.reply_text(
                "К сожалению, сейчас нет доступных челленджей.",
                reply_markup=get_main_menu_keyboard()
            )
    
    elif text == "👥 Позвать друга":
        user = await db.get_user(update.effective_user.id)
        await update.message.reply_text(
            f"Пригласите друга по ссылке:\n"
            f"https://t.me/SparkaphBot?start={user['referral_code']}",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif text == "🏆 Мои награды":
        user = await db.get_user(update.effective_user.id)
        badges_text = "\n".join([BADGES[badge] for badge in user['badges']]) if user['badges'] else "У вас пока нет наград"
        await update.message.reply_text(
            f"Ваши награды:\n\n{badges_text}",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif text == "⚙️ Настройки":
        await update.message.reply_text(
            "Настройки:\n\n"
            "1. Язык\n"
            "2. Уведомления\n"
            "3. Аккаунт",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif text == "❓ Помощь":
        await update.message.reply_text(
            "Часто задаваемые вопросы:\n\n"
            "1. Как начать участвовать?\n"
            "2. Как отправлять видео?\n"
            "3. Как работают награды?\n"
            "4. Как пригласить друга?\n\n"
            "Выберите вопрос или напишите свой:",
            reply_markup=get_main_menu_keyboard()
        )
    
    return UserStates.MAIN_MENU

async def handle_challenge_selection(update: Update, context):
    """Обработчик выбора челленджа."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("category_"):
        category = query.data.split("_")[1]
        challenges = await db.get_active_challenges(category)
        if challenges:
            challenge = challenges[0]  # Показываем первый челлендж
            await query.message.edit_text(
                format_challenge_info(challenge),
                reply_markup=get_challenge_actions_keyboard(challenge['challenge_id'])
            )
        else:
            await query.message.edit_text(
                "В этой категории пока нет челленджей.",
                reply_markup=get_categories_keyboard()
            )
    
    elif query.data.startswith("start_challenge_"):
        challenge_id = int(query.data.split("_")[2])
        await query.message.edit_text(
            "Снимите короткое видео (до 60 секунд) и отправьте его сюда:",
            reply_markup=get_main_menu_keyboard()
        )
        context.user_data['current_challenge'] = challenge_id
        return UserStates.SENDING_VIDEO
    
    elif query.data == "back_to_main":
        await query.message.edit_text(
            "Главное меню:",
            reply_markup=get_main_menu_keyboard()
        )
        return UserStates.MAIN_MENU

async def handle_video_submission(update: Update, context):
    """Обработчик отправки видео."""
    if not update.message.video:
        await update.message.reply_text(
            "Пожалуйста, отправьте видео.",
            reply_markup=get_main_menu_keyboard()
        )
        return UserStates.SENDING_VIDEO
    
    video = update.message.video
    if not validate_video_duration(video.duration):
        await update.message.reply_text(
            "Видео должно быть не длиннее 60 секунд.",
            reply_markup=get_main_menu_keyboard()
        )
        return UserStates.SENDING_VIDEO
    
    challenge_id = context.user_data.get('current_challenge')
    if not challenge_id:
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, выберите челлендж заново.",
            reply_markup=get_main_menu_keyboard()
        )
        return UserStates.MAIN_MENU
    
    # Создаем запись о видео
    submission = {
        "user_id": update.effective_user.id,
        "challenge_id": challenge_id,
        "video_file_id": video.file_id,
        "status": "pending"
    }
    await db.create_submission(submission)
    
    await update.message.reply_text(
        "Ваше видео отправлено на модерацию! Мы сообщим вам о результате.",
        reply_markup=get_main_menu_keyboard()
    )
    return UserStates.MAIN_MENU

def main():
    """Запуск бота."""
    application = Application.builder().token(USER_BOT_TOKEN).build()
    
    # Создаем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            UserStates.ONBOARDING: [
                CallbackQueryHandler(handle_onboarding)
            ],
            UserStates.LANGUAGE_SELECTION: [
                CallbackQueryHandler(handle_language_selection)
            ],
            UserStates.MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)
            ],
            UserStates.VIEWING_CHALLENGES: [
                CallbackQueryHandler(handle_challenge_selection)
            ],
            UserStates.SENDING_VIDEO: [
                MessageHandler(filters.VIDEO, handle_video_submission)
            ]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main() 