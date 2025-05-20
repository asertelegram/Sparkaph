import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Токены ботов
USER_BOT_TOKEN = os.getenv('USER_BOT_TOKEN')
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
INFLUENCER_BOT_TOKEN = os.getenv('INFLUENCER_BOT_TOKEN')

# Настройки базы данных
MONGODB_URI = os.getenv('MONGODB_URI')
DATABASE_NAME = 'Sparkaph'

# Настройки канала
CHANNEL_ID = os.getenv('CHANNEL_ID')

# ID администратора
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# Тип бота
BOT_TYPE = os.getenv('BOT_TYPE', 'all')

# Настройки для пользовательского бота
WELCOME_MESSAGE = """
👋 Добро пожаловать в Sparkaph!

🎯 Проходи челленджи, снимай видео — попадай в топ и получай фидбэк!

Выберите действие:
"""

# Категории челленджей
CHALLENGE_CATEGORIES = [
    "Фаст",
    "Смешные",
    "Умные",
    "Танцы",
    "Креатив",
    "Спорт",
    "Музыка",
    "Другое"
]

# Настройки геймификации
BADGES = {
    "newbie": "🌱 Новичок",
    "active": "🔥 Активный",
    "creative": "🎨 Креативный",
    "popular": "⭐ Популярный",
    "streak_3": "🔥 3 дня подряд",
    "streak_7": "🔥 7 дней подряд",
    "streak_30": "🔥 30 дней подряд",
    "referral": "👥 Привел друга"
}

# Настройки для модерации
MODERATION_TIMEOUT = 24 * 60 * 60  # 24 часа в секундах 