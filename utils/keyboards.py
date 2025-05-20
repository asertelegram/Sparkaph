from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import CHALLENGE_CATEGORIES

# Общие клавиатуры
def get_main_menu_keyboard(is_admin: bool = False, is_influencer: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("🎯 Челленджи"), KeyboardButton("📱 Мои челленджи")],
        [KeyboardButton("📊 Лидерборд"), KeyboardButton("🎲 Рандом челлендж")],
        [KeyboardButton("👥 Позвать друга"), KeyboardButton("🏆 Мои награды")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("❓ Помощь")]
    ]
    
    if is_admin:
        buttons.append([KeyboardButton("🔧 Админ-панель")])
    elif is_influencer:
        buttons.append([KeyboardButton("📈 Статистика блогера")])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_categories_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for category in CHALLENGE_CATEGORIES:
        buttons.append([InlineKeyboardButton(category, callback_data=f"category_{category}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)

def get_challenge_actions_keyboard(challenge_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("✅ Начать", callback_data=f"start_challenge_{challenge_id}"),
            InlineKeyboardButton("⭐ В избранное", callback_data=f"favorite_{challenge_id}")
        ],
        [
            InlineKeyboardButton("📱 Поделиться", callback_data=f"share_{challenge_id}"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_challenges")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

# Клавиатуры для пользовательского бота
def get_onboarding_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("❓ Что это?", callback_data="what_is_this")],
        [InlineKeyboardButton("🎯 Как участвовать?", callback_data="how_to_participate")],
        [InlineKeyboardButton("📱 Посмотреть примеры", callback_data="view_examples")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

def get_leaderboard_period_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📅 День", callback_data="leaderboard_day"),
            InlineKeyboardButton("📅 Неделя", callback_data="leaderboard_week")
        ],
        [InlineKeyboardButton("📅 Все время", callback_data="leaderboard_all")]
    ]
    return InlineKeyboardMarkup(buttons)

# Клавиатуры для админ-бота
def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📝 Модерация видео", callback_data="moderate_videos")],
        [InlineKeyboardButton("➕ Добавить челлендж", callback_data="add_challenge")],
        [InlineKeyboardButton("👥 Управление блогерами", callback_data="manage_influencers")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_moderation_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{submission_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{submission_id}")
        ],
        [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_{submission_id}")]
    ]
    return InlineKeyboardMarkup(buttons)

# Клавиатуры для блогерского бота
def get_influencer_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("➕ Создать челлендж", callback_data="create_challenge")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="influencer_stats")],
        [InlineKeyboardButton("📱 Мои челленджи", callback_data="my_challenges")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_challenge_creation_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📝 Название", callback_data="challenge_title")],
        [InlineKeyboardButton("📄 Описание", callback_data="challenge_description")],
        [InlineKeyboardButton("📁 Медиа", callback_data="challenge_media")],
        [InlineKeyboardButton("✅ Опубликовать", callback_data="publish_challenge")]
    ]
    return InlineKeyboardMarkup(buttons)

# Вспомогательные клавиатуры
def get_confirmation_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"cancel_{action}_{item_id}")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

def get_pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    if current_page > 1:
        buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}_page_{current_page-1}"))
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}_page_{current_page+1}"))
    return InlineKeyboardMarkup([buttons]) 