import os
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any, Union
import asyncio
import random
import base64
from bson import ObjectId
import ssl
import certifi
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
import io

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Установка глобального флага для имитации успешного подключения к MongoDB
MOCK_DB = False  # Установите в True для отладки без MongoDB

# Инициализация бота и диспетчера
try:
    USER_BOT_TOKEN = os.getenv("USER_BOT_TOKEN")
    if not USER_BOT_TOKEN:
        raise ValueError("USER_BOT_TOKEN отсутствует в .env файле")
    
    bot = Bot(token=USER_BOT_TOKEN)
    dp = Dispatcher()
    logger.info("Бот инициализирован успешно")
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    raise

# Создаем заглушку для MongoDB, если не удается подключиться
class MockDB:
    """Класс-заглушка для операций с базой данных, когда MongoDB недоступна."""
    
    def __init__(self):
        self.users = MockCollection("users")
        self.categories = MockCollection("categories")
        self.challenges = MockCollection("challenges")
        self.submissions = MockCollection("submissions")
    
    def __getattr__(self, name):
        # Динамически создаем коллекции по мере необходимости
        return MockCollection(name)

class MockCollection:
    """Имитация коллекции MongoDB."""
    
    def __init__(self, name):
        self.name = name
        self.data = []
        logger.warning(f"Используется заглушка для коллекции {name}")
    
    async def find_one(self, query=None, *args, **kwargs):
        logger.warning(f"Вызов find_one для {self.name} с заглушкой БД")
        # Для тестирования пользователя
        if self.name == "users" and query and query.get("user_id"):
            return {"user_id": query["user_id"], "username": "user", "points": 0, "current_challenge": None}
        return None
    
    async def find(self, query=None, *args, **kwargs):
        logger.warning(f"Вызов find для {self.name} с заглушкой БД")
        return MockCursor([])
    
    async def insert_one(self, document, *args, **kwargs):
        logger.warning(f"Вызов insert_one для {self.name} с заглушкой БД")
        return MockResult()
    
    async def update_one(self, query, update, *args, **kwargs):
        logger.warning(f"Вызов update_one для {self.name} с заглушкой БД")
        return MockResult()
    
    async def count_documents(self, query=None, *args, **kwargs):
        logger.warning(f"Вызов count_documents для {self.name} с заглушкой БД")
        return 0

class MockCursor:
    """Имитация курсора MongoDB."""
    
    def __init__(self, data):
        self.data = data
    
    async def to_list(self, length=None):
        return []

class MockResult:
    """Имитация результата операции MongoDB."""
    
    @property
    def inserted_id(self):
        return ObjectId()

# Инициализация клиента MongoDB
try:
    logger.info("Попытка подключения к MongoDB...")
    
    # Сначала пробуем обычное подключение
    mongodb_uri = os.getenv("MONGODB_URI", "")
    
    if not mongodb_uri:
        logger.error("MONGODB_URI не найден в .env файле")
        if not MOCK_DB:
            MOCK_DB = True
            logger.warning("Переключение на MOCK_DB из-за отсутствия URI")
    
    if not MOCK_DB:
        try:
            # Добавляем параметры для обхода проблем с SSL
            if "?" in mongodb_uri:
                if "tlsAllowInvalidCertificates=true" not in mongodb_uri:
                    mongodb_uri += "&tlsAllowInvalidCertificates=true"
            else:
                mongodb_uri += "?tlsAllowInvalidCertificates=true"
            
            # Создаем клиента без строгой проверки TLS
            mongo_client = AsyncIOMotorClient(
                mongodb_uri,
                tlsAllowInvalidCertificates=True,  # Оставляем только эту опцию
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                serverSelectionTimeoutMS=10000,
                heartbeatFrequencyMS=15000,
                retryWrites=False,
            )
            
            # Получаем ссылку на базу данных
            db = mongo_client.Sparkaph
            logger.info("MongoDB клиент инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации MongoDB клиента: {e}")
            MOCK_DB = True
    
    if MOCK_DB:
        logger.warning("Используется заглушка вместо MongoDB")
        db = MockDB()

except Exception as e:
    logger.error(f"Критическая ошибка при инициализации MongoDB: {e}")
    # Даже при ошибке продолжаем работу с заглушкой
    db = MockDB()
    MOCK_DB = True

# Обработчик для отладки MongoDB подключения
@dp.message(Command("dbtest"))
async def cmd_dbtest(message: Message):
    try:
        await message.answer("Проверка подключения к MongoDB...")
        
        if MOCK_DB:
            await message.answer("⚠️ Используется заглушка вместо MongoDB")
            return
        
        # Проверяем подключение
        try:
            # Используем более короткий таймаут для проверки
            result = await mongo_client.admin.command("ping", serverSelectionTimeoutMS=5000)
            await message.answer(f"✅ MongoDB подключение работает!\nРезультат: {result}")
            
            # Проверяем доступность базы
            collections = await db.list_collection_names()
            await message.answer(f"📊 Доступные коллекции: {', '.join(collections) if collections else 'нет'}")
        except Exception as e:
            await message.answer(f"❌ Ошибка подключения к MongoDB: {e}")
    except Exception as e:
        logger.error(f"Ошибка при проверке MongoDB: {e}")
        await message.answer(f"Произошла ошибка: {e}")

# ID канала
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
if not CHANNEL_ID:
    logger.warning("CHANNEL_ID не установлен в .env файле")

# Состояния
class UserStates(StatesGroup):
    waiting_for_challenge_submission = State()
    selecting_category = State()
    waiting_for_media = State()
    registering_gender = State() 
    registering_age = State()
    registering_location = State()

# Бейджи и их условия
BADGES = {
    "first_challenge": {
        "name": "🎯 Первый шаг",
        "description": "Выполнил свой первый челлендж"
    },
    "streak_3": {
        "name": "🔥 Горячая серия",
        "description": "3 дня подряд выполнял челленджи"
    },
    "streak_7": {
        "name": "⚡ Неделя силы",
        "description": "7 дней подряд выполнял челленджи"
    },
    "streak_30": {
        "name": "🌟 Легенда",
        "description": "30 дней подряд выполнял челленджи"
    },
    "invite_5": {
        "name": "👥 Социальная бабочка",
        "description": "Пригласил 5 друзей"
    },
    "challenges_10": {
        "name": "🏆 Десяточка",
        "description": "Выполнил 10 челленджей"
    },
    "challenges_50": {
        "name": "💫 Мастер",
        "description": "Выполнил 50 челленджей"
    },
    "challenges_100": {
        "name": "👑 Легенда",
        "description": "Выполнил 100 челленджей"
    }
}

# Константы для системы уровней
LEVELS = {
    1: {"points": 0, "name": "Новичок"},
    2: {"points": 100, "name": "Исследователь"},
    3: {"points": 300, "name": "Активист"},
    4: {"points": 600, "name": "Энтузиаст"},
    5: {"points": 1000, "name": "Мастер"},
    6: {"points": 1500, "name": "Гуру"},
    7: {"points": 2100, "name": "Легенда"},
    8: {"points": 2800, "name": "Император"},
    9: {"points": 3600, "name": "Титан"},
    10: {"points": 4500, "name": "Бог"}
}

# Константы для ежедневных бонусов
DAILY_BONUSES = {
    1: 10,  # 1 день - 10 очков
    2: 15,  # 2 дня - 15 очков
    3: 20,  # 3 дня - 20 очков
    4: 25,  # 4 дня - 25 очков
    5: 30,  # 5 дней - 30 очков
    6: 35,  # 6 дней - 35 очков
    7: 50   # 7 дней - 50 очков
}

# Функция для проверки и обновления streak
async def update_streak(user_id: int) -> tuple:
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return 0, 0
    
    now = datetime.now(UTC)
    last_daily = user.get("last_daily")
    current_streak = user.get("streak", 0)
    
    if not last_daily:
        # Первый вход
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_daily": now, "streak": 1}}
        )
        return 1, DAILY_BONUSES[1]
    
    # Проверяем, прошло ли 24 часа с последнего входа
    time_diff = now - last_daily
    if time_diff.days >= 2:
        # Streak прерван
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_daily": now, "streak": 1}}
        )
        return 1, DAILY_BONUSES[1]
    elif time_diff.days == 1:
        # Streak продолжается
        new_streak = min(current_streak + 1, 7)
        bonus = DAILY_BONUSES[new_streak]
        
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"last_daily": now, "streak": new_streak},
                "$inc": {"points": bonus}
            }
        )
        return new_streak, bonus
    else:
        # Уже получил бонус сегодня
        return current_streak, 0

# Функция для выдачи бейджа
async def award_badge(user_id: int, badge_id: str):
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return
    
    badges = user.get("badges", [])
    if badge_id not in badges:
        badges.append(badge_id)
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"badges": badges}}
        )
        
        # Отправляем уведомление о новом бейдже
        badge = BADGES[badge_id]
        await bot.send_message(
            user_id,
            f"🏆 Поздравляем! Вы получили новый бейдж:\n\n"
            f"{badge['name']}\n"
            f"{badge['description']}"
        )

# Проверка подписки на канал
async def check_subscription(user_id: int) -> bool:
    if not CHANNEL_ID:
        logger.warning("Невозможно проверить подписку: CHANNEL_ID не установлен")
        return True  # Если канал не настроен, считаем что пользователь подписан
    
    try:
        # Получаем информацию о пользователе в канале
        chat_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        # Статусы, означающие, что пользователь подписан
        return chat_member.status in ['creator', 'administrator', 'member']
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        # В случае ошибки возвращаем True, чтобы не блокировать пользователя
        return True

# Функция для получения уровня пользователя
async def get_user_level(points: int) -> int:
    for level, data in sorted(LEVELS.items(), reverse=True):
        if points >= data["points"]:
            return level
    return 1

# Функция для получения прогресса до следующего уровня
async def get_level_progress(points: int) -> tuple:
    current_level = await get_user_level(points)
    if current_level >= 10:
        return 100, 0
    
    current_level_points = LEVELS[current_level]["points"]
    next_level_points = LEVELS[current_level + 1]["points"]
    points_needed = next_level_points - current_level_points
    points_have = points - current_level_points
    
    progress = (points_have / points_needed) * 100
    return progress, points_needed - points_have

# Функция для генерации реферальной ссылки
async def generate_referral_link(user_id: int) -> str:
    bot_username = (await bot.get_me()).username
    return f"https://t.me/{bot_username}?start=ref{user_id}"

# Функция для обработки реферального кода
async def process_referral_code(user_id: int, ref_code: str) -> bool:
    try:
        ref_id = int(ref_code[3:])  # Убираем 'ref' из кода
        if ref_id == user_id:
            return False
        
        # Проверяем, не был ли уже использован реферальный код
        user = await db.users.find_one({"user_id": user_id})
        if user and user.get("referred_by"):
            return False
        
        # Обновляем информацию о реферале
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"referred_by": ref_id}}
        )
        
        # Начисляем очки рефереру
        await db.users.update_one(
            {"user_id": ref_id},
            {"$inc": {"points": 20}}
        )
        
        return True
    except:
        return False

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "Unknown"
        
        # Проверяем реферальный код
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("ref"):
            await process_referral_code(user_id, args[1])
        
        # Получаем или создаем пользователя
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id": user_id,
                "username": username,
                "points": 0,
                "level": 1,
                "challenges_completed": 0,
                "created_at": datetime.now(UTC),
                "last_activity": datetime.now(UTC),
                "streak": 0,
                "last_daily": None,
                "notifications_disabled": False
            }
            await db.users.insert_one(user)
        
        # Проверяем ежедневный бонус
        streak, bonus = await update_streak(user_id)
        
        # Получаем уровень и прогресс
        level = await get_user_level(user["points"])
        progress, points_needed = await get_level_progress(user["points"])
        
        # Генерируем реферальную ссылку
        ref_link = await generate_referral_link(user_id)
        
        welcome_text = (
            f"👋 Привет, {username}!\n\n"
            f"🎯 Твой уровень: {level} ({LEVELS[level]['name']})\n"
            f"💎 Очков: {user['points']}\n"
            f"📊 Прогресс до следующего уровня: {progress:.1f}%\n"
            f"   Осталось очков: {points_needed}\n"
            f"🔥 Твой streak: {streak} дней\n"
        )
        
        if bonus > 0:
            welcome_text += f"🎁 Получен ежедневный бонус: +{bonus} очков!\n\n"
        
        welcome_text += (
            f"🔗 Твоя реферальная ссылка:\n{ref_link}\n\n"
            f"Приглашай друзей и получай +20 очков за каждого!"
        )
        
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🎯 Челленджи"), types.KeyboardButton(text="📊 Мой рейтинг")],
                [types.KeyboardButton(text="✅ Мои достижения"), types.KeyboardButton(text="👥 Пригласить друга")],
                [types.KeyboardButton(text="🔔 Уведомления"), types.KeyboardButton(text="📞 Поддержка")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(welcome_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(UserStates.registering_gender, F.data.startswith("gender_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    # Сохраняем пол пользователя
    if gender != "skip":
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"gender": gender}}
        )
    
    # Запрашиваем возраст
    await callback.message.edit_text(
        "Сколько вам лет? Выберите диапазон:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="до 18", callback_data="age_under18")],
                [InlineKeyboardButton(text="18-24", callback_data="age_18-24")],
                [InlineKeyboardButton(text="25-34", callback_data="age_25-34")],
                [InlineKeyboardButton(text="35-44", callback_data="age_35-44")],
                [InlineKeyboardButton(text="45+", callback_data="age_45plus")],
                [InlineKeyboardButton(text="Пропустить", callback_data="age_skip")]
            ]
        )
    )
    
    await state.set_state(UserStates.registering_age)
    await callback.answer()

@dp.callback_query(UserStates.registering_age, F.data.startswith("age_"))
async def process_age(callback: CallbackQuery, state: FSMContext):
    age = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    # Сохраняем возраст пользователя
    if age != "skip":
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"age": age}}
        )
    
    # Финализируем регистрацию
    await finalize_registration(callback.message, user_id)
    await state.clear()
    await callback.answer()

async def finalize_registration(message: Message, user_id: int):
    # Проверяем подписку на канал
    is_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        # Если пользователь уже подписан, обновляем статус и начисляем бонус
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"subscription": True}, "$inc": {"points": 10}}
        )
        
        await message.edit_text(
            "Регистрация завершена! Спасибо за информацию.\n\n"
            "Вы уже подписаны на наш канал! +10 очков бонус.\n\n"
            "Выберите действие в меню ниже:",
            reply_markup=None
        )
        
        # Отправляем сообщение с главным меню
        await message.answer("Главное меню:", reply_markup=get_main_menu())
    else:
        # Создаем кнопку для перехода в канал
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
            ]
        )
        
        await message.edit_text(
            "Регистрация завершена! Спасибо за информацию.\n\n"
            "Для доступа к челленджам подпишитесь на наш канал.\n"
            "После подписки вы получите 10 очков бонуса!",
            reply_markup=keyboard
        )
        
        # Отправляем сообщение с главным меню
        await message.answer("Главное меню:", reply_markup=get_main_menu())

# Клавиатура главного меню
def get_main_menu():
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🎯 Челленджи")],
            [types.KeyboardButton(text="📊 Мой рейтинг"), types.KeyboardButton(text="✅ Мои достижения")],
            [types.KeyboardButton(text="👥 Пригласить друга"), types.KeyboardButton(text="📞 Поддержка")],
            [types.KeyboardButton(text="🎡 Колесо фортуны"), types.KeyboardButton(text="🎨 Генератор обложек")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик перехода в меню челленджей
@dp.message(F.text == "🎯 Челленджи")
async def show_challenge_categories(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            await message.answer("Сначала зарегистрируйся через /start")
            return
        
        # Автоматическая проверка подписки
        is_subscribed = await check_subscription(user_id)
        subscription_changed = False
        
        if is_subscribed and not user.get("subscription"):
            # Обновляем статус подписки и начисляем очки
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"subscription": True}, "$inc": {"points": 10}}
            )
            await message.answer("Спасибо за подписку! Тебе начислено 10 очков.")
            subscription_changed = True
        elif not is_subscribed and user.get("subscription"):
            # Если пользователь отписался
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"subscription": False}}
            )
            
            # Создаем кнопку для перехода в канал
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
                ]
            )
            
            await message.answer(
                "⚠️ Вы отписались от нашего канала!\n"
                "Для доступа к челленджам необходимо подписаться на канал.",
                reply_markup=keyboard
            )
            return
        
        if not is_subscribed:
            # Создаем кнопку для перехода в канал
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
                ]
            )
            
            await message.answer(
                "Для получения челленджей необходимо подписаться на канал.\n"
                "После подписки ты получишь 10 очков!",
                reply_markup=keyboard
            )
            return
        
        # Проверка текущего челленджа
        if user.get("current_challenge"):
            # Если у пользователя уже есть активный челлендж
            challenge = await db.challenges.find_one({"_id": user["current_challenge"]})
            if challenge:
                category = await db.categories.find_one({"_id": challenge.get("category_id")})
                category_name = category.get("name", "Неизвестная категория") if category else "Неизвестная категория"
                
                # Формируем описание челленджа
                challenge_description = challenge.get("description", "")
                
                text = (
                    f"🎯 У тебя уже есть активный челлендж!\n\n"
                    f"Категория: {category_name}\n"
                    f"Челлендж: {challenge['text']}\n"
                )
                
                if challenge_description:
                    text += f"\nОписание: {challenge_description}\n"
                
                text += "\nВыполни его или пропусти, чтобы получить новый."
                
                await message.answer(text, reply_markup=get_challenge_menu())
                return
        
        # Получаем все категории челленджей
        categories = await db.categories.find().to_list(length=None)
        
        if not categories:
            await message.answer("К сожалению, категории пока не созданы. Попробуй позже.")
            return
        
        # Создаем inline-клавиатуру с категориями
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for category in categories:
            # Получаем количество доступных челленджей в категории
            available_challenges = await db.challenges.count_documents({
                "category_id": category["_id"],
                "status": "active",
                "$expr": {"$lt": [{"$size": "$taken_by"}, 5]}
            })
            
            if available_challenges > 0:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"{category['name']} ({available_challenges})", 
                        callback_data=f"category_{category['_id']}"
                    )
                ])
        
        if len(keyboard.inline_keyboard) > 0:
            await message.answer("Выбери категорию челленджа:", reply_markup=keyboard)
            await state.set_state(UserStates.selecting_category)
        else:
            await message.answer("К сожалению, сейчас нет доступных челленжей ни в одной категории. Попробуй позже.")
        
    except Exception as e:
        logger.error(f"Ошибка при показе категорий челленджей: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

def get_challenge_menu():
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📸 Отправить фото или видео")],
            [types.KeyboardButton(text="🚫 Пропустить челлендж")],
            [types.KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик выбора категории
@dp.callback_query(UserStates.selecting_category, F.data.startswith("category_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        
        try:
            category_id = ObjectId(callback.data.split("_")[1])
        except Exception as e:
            logger.error(f"Ошибка при преобразовании ID категории: {e}")
            await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте снова.")
            await state.clear()
            return
        
        # Получаем информацию о категории
        category = await db.categories.find_one({"_id": category_id})
        if not category:
            await callback.message.edit_text("Категория не найдена. Пожалуйста, попробуйте снова.")
            await state.clear()
            return
        
        category_name = category["name"]
        category_description = category.get("description", "")
        
        # Получение случайного челленджа из выбранной категории
        challenges = await db.challenges.find({
            "category_id": category_id,
            "status": "active",
            "$expr": {"$lt": [{"$size": "$taken_by"}, 5]}
        }).to_list(length=None)
        
        if not challenges:
            await callback.message.edit_text("К сожалению, в этой категории нет доступных челленджей.")
            await state.clear()
            return
        
        # Выбираем случайный челлендж из доступных
        challenge = random.choice(challenges)
        challenge_description = challenge.get("description", "")
        
        # Текущее время
        current_time = datetime.now(UTC)
        
        # Обновление текущего челленджа пользователя
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "current_challenge": challenge["_id"],
                    "challenge_started_at": current_time,
                    "first_reminder_sent": False,
                    "second_reminder_sent": False
                }
            }
        )
        
        # Добавление пользователя в список участников челленджа
        await db.challenges.update_one(
            {"_id": challenge["_id"]},
            {"$push": {"taken_by": user_id}}
        )
        
        # Формируем текст с описанием челленджа
        text = f"🎯 Твой челлендж (Категория: {category_name}):\n\n"
        text += f"{challenge['text']}\n\n"
        
        if challenge_description:
            text += f"Описание: {challenge_description}\n\n"
        
        if category_description:
            text += f"О категории: {category_description}\n\n"
        
        text += "У тебя есть 12 часов на выполнение.\nОтправь результат в виде текста, фото, видео или документа."
        
        await callback.message.edit_text(text)
        
        # Отправляем клавиатуру в новом сообщении
        await callback.message.answer("Выбери действие:", reply_markup=get_challenge_menu())
        
        # Устанавливаем состояние ожидания результата
        await state.set_state(UserStates.waiting_for_challenge_submission)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при выборе категории челленджа: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик запроса на отправку медиа
@dp.message(F.text == "📸 Отправить фото или видео")
async def request_media(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await db.users.find_one({"user_id": user_id})
    
    if not user or not user.get("current_challenge"):
        await message.answer("У тебя нет активного челленджа. Получи новый челлендж сначала.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    await message.answer(
        "Пожалуйста, отправь фото или видео с результатом челленджа.\n\n"
        "Подсказка: можешь добавить текстовое описание к медиа."
    )
    await state.set_state(UserStates.waiting_for_media)

# Обработчик пропуска челленджа
@dp.message(F.text == "🚫 Пропустить челлендж")
async def skip_challenge(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await db.users.find_one({"user_id": user_id})
    if user and user.get("current_challenge"):
        # Удаляем пользователя из списка взявших челлендж
        await db.challenges.update_one(
            {"_id": user["current_challenge"]},
            {"$pull": {"taken_by": user_id}}
        )
        
        # Обнуляем текущий челлендж пользователя
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"current_challenge": None}}
        )
        
        await message.answer("Челлендж пропущен. Ты можешь получить новый в меню челленджей.", reply_markup=get_main_menu())
    else:
        await message.answer("У тебя нет активного челленджа.", reply_markup=get_main_menu())
    await state.clear()

# Обработчик возврата в главное меню
@dp.message(F.text == "🏠 Главное меню")
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_menu())

# Обработчик отправки медиа
@dp.message(UserStates.waiting_for_media)
async def handle_media_submission(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user or not user.get("current_challenge"):
            await message.answer("У тебя нет активного челленджа.", reply_markup=get_main_menu())
            await state.clear()
            return
        
        media = None
        media_type = ""
        file_content = None
        
        if message.photo:
            # Берем последнее фото (с наилучшим качеством)
            media = message.photo[-1].file_id
            media_type = "photo"
            logger.info(f"Получено фото с file_id: {media}")
            
            # Скачиваем файл
            try:
                file = await bot.get_file(media)
                file_path = file.file_path
                file_content_bytes = await bot.download_file(file_path)
                # Конвертируем содержимое файла в base64 для хранения в MongoDB
                file_content = base64.b64encode(file_content_bytes.read()).decode('utf-8')
                logger.info(f"Фото успешно скачано и закодировано, размер: {len(file_content)}")
            except Exception as e:
                logger.error(f"Ошибка при скачивании фото: {e}")
        elif message.video:
            media = message.video.file_id
            media_type = "video"
            logger.info(f"Получено видео с file_id: {media}")
            
            # Скачиваем файл
            try:
                file = await bot.get_file(media)
                file_path = file.file_path
                file_content_bytes = await bot.download_file(file_path)
                # Конвертируем содержимое файла в base64 для хранения в MongoDB
                file_content = base64.b64encode(file_content_bytes.read()).decode('utf-8')
                logger.info(f"Видео успешно скачано и закодировано, размер: {len(file_content)}")
            except Exception as e:
                logger.error(f"Ошибка при скачивании видео: {e}")
        elif message.document:
            media = message.document.file_id
            media_type = "document"
            logger.info(f"Получен документ с file_id: {media}")
            
            # Скачиваем файл
            try:
                file = await bot.get_file(media)
                file_path = file.file_path
                file_content_bytes = await bot.download_file(file_path)
                # Конвертируем содержимое файла в base64 для хранения в MongoDB
                file_content = base64.b64encode(file_content_bytes.read()).decode('utf-8')
                logger.info(f"Документ успешно скачан и закодирован, размер: {len(file_content)}")
            except Exception as e:
                logger.error(f"Ошибка при скачивании документа: {e}")
        elif message.text:
            # Если пользователь отправил текст вместо медиа
            media_type = "text"
        
        # Если медиафайл не обнаружен, но это не текстовый режим
        if not media and not media_type == "text":
            await message.answer(
                "Не обнаружено фото или видео. Пожалуйста, попробуйте снова или отправьте текстовый ответ."
            )
            return
        
        challenge_id = user["current_challenge"]
        
        submission = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "text": message.caption if message.caption else (message.text if message.text else "Отправка медиа"),
            "media": media,
            "media_type": media_type,
            "submitted_at": datetime.now(UTC),
            "status": "pending",
            "file_content": file_content  # Добавляем содержимое файла
        }
        
        # Логируем данные для отладки
        logger.info(f"Сохраняем отправку с media_type: {media_type}, media: {media}, содержимое файла: {'сохранено' if file_content else 'не сохранено'}")
        
        await db.submissions.insert_one(submission)
        
        # Очистка текущего челленджа и удаление из списка взявших
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"current_challenge": None}}
        )
        
        await db.challenges.update_one(
            {"_id": challenge_id},
            {"$pull": {"taken_by": user_id}}
        )
        
        await message.answer(
            "✅ Твой результат отправлен на проверку!\n"
            "После проверки ты получишь уведомление.",
            reply_markup=get_main_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при отправке медиа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.", reply_markup=get_main_menu())
        await state.clear()

# Обработчик отправки челленджа (текст)
@dp.message(UserStates.waiting_for_challenge_submission)
async def handle_challenge_submission(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user or not user.get("current_challenge"):
            await message.answer("У тебя нет активного челленджа.", reply_markup=get_main_menu())
            await state.clear()
            return
        
        challenge_id = user["current_challenge"]
        
        # Проверяем, содержит ли сообщение медиа
        media = None
        media_type = "text"
        file_content = None
        
        if message.photo:
            media = message.photo[-1].file_id
            media_type = "photo"
        elif message.video:
            media = message.video.file_id
            media_type = "video"
        elif message.document:
            media = message.document.file_id
            media_type = "document"
        
        submission = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "text": message.caption if message.caption else (message.text if message.text else "Отправка медиа"),
            "media": media,
            "media_type": media_type,
            "submitted_at": datetime.now(UTC),
            "status": "pending",
            "file_content": file_content
        }
        
        await db.submissions.insert_one(submission)
        
        # Очистка текущего челленджа и удаление из списка взявших
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"current_challenge": None}}
        )
        
        await db.challenges.update_one(
            {"_id": challenge_id},
            {"$pull": {"taken_by": user_id}}
        )
        
        # Обновляем streak и проверяем бейджи
        await update_streak(user_id)
        
        # Проверяем бейдж за первый челлендж
        if len(user.get("completed_challenges", [])) == 0:
            await award_badge(user_id, "first_challenge")
        
        await message.answer(
            "✅ Твой результат отправлен на проверку!\n"
            "После проверки ты получишь уведомление.",
            reply_markup=get_main_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при отправке челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.", reply_markup=get_main_menu())
        await state.clear()

# Обработчик рейтинга
@dp.message(F.text == "📊 Мой рейтинг")
async def show_rating(message: Message):
    try:
        user_id = message.from_user.id
        
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            await message.answer("Сначала зарегистрируйся через /start")
            return
        
        # Получение места в рейтинге
        users_with_higher_points = await db.users.count_documents({
            "points": {"$gt": user.get("points", 0)}
        })
        total_users = await db.users.count_documents({})
        rank = users_with_higher_points + 1
        
        # Получение топ-10 пользователей
        top_users = await db.users.find().sort("points", -1).limit(10).to_list(length=None)
        
        # Формируем текст рейтинга
        text = (
            f"📊 Твой рейтинг:\n\n"
            f"Очки: {user.get('points', 0)}\n"
            f"Место: {rank} из {total_users}\n\n"
            f"🏆 Топ-10 пользователей:\n"
        )
        
        for i, top_user in enumerate(top_users, 1):
            username = top_user.get("username", "Неизвестно")
            if not username:
                username = f"Пользователь {top_user['user_id']}"
            
            text += f"{i}. @{username} - {top_user.get('points', 0)} очков\n"
            
            # Если это текущий пользователь, добавляем метку
            if top_user["user_id"] == user_id:
                text = text[:-1] + " (это ты) 👑\n"
        
        completed_challenges = len(user.get("completed_challenges", []))
        text += f"\nВыполнено челленджей: {completed_challenges}"
        
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка при показе рейтинга: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик достижений
@dp.message(F.text == "✅ Мои достижения")
async def show_achievements(message: Message):
    try:
        user_id = message.from_user.id
        
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            await message.answer("Сначала зарегистрируйся через /start")
            return
        
        completed = user.get("completed_challenges", [])
        total_completed = len(completed)
        
        if not completed:
            await message.answer(
                "У тебя пока нет выполненных челленджей.\n"
                "Выбери категорию и начни выполнять задания!"
            )
            return
        
        # Получение последних 5 выполненных челленджей
        recent_challenges = []
        for challenge_id in completed[-5:]:
            challenge = await db.challenges.find_one({"_id": challenge_id})
            if challenge:
                category = await db.categories.find_one({"_id": challenge.get("category_id")})
                category_name = category.get("name", "Неизвестная категория") if category else "Неизвестная категория"
                recent_challenges.append({
                    "text": challenge["text"],
                    "category": category_name
                })
        
        # Получение статистики по категориям
        category_stats = {}
        for challenge_id in completed:
            challenge = await db.challenges.find_one({"_id": challenge_id})
            if challenge and challenge.get("category_id"):
                category = await db.categories.find_one({"_id": challenge["category_id"]})
                if category:
                    category_name = category["name"]
                    if category_name in category_stats:
                        category_stats[category_name] += 1
                    else:
                        category_stats[category_name] = 1
        
        # Формируем текст достижений
        text = (
            f"✅ Твои достижения:\n\n"
            f"Выполнено челленджей: {total_completed}\n"
            f"Текущая серия: {user.get('streak', 0)} дней 🔥\n\n"
        )
        
        # Добавляем бейджи
        badges = user.get("badges", [])
        if badges:
            text += "🏆 Твои бейджи:\n"
            for badge_id in badges:
                badge = BADGES[badge_id]
                text += f"• {badge['name']} - {badge['description']}\n"
            text += "\n"
        
        # Добавляем статистику по категориям
        if category_stats:
            text += "По категориям:\n"
            for category_name, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                text += f"• {category_name}: {count}\n"
            text += "\n"
        
        # Добавляем последние выполненные челленджи
        if recent_challenges:
            text += "Недавно выполненные:\n"
            for i, challenge in enumerate(reversed(recent_challenges), 1):
                text += f"{i}. {challenge['text']} ({challenge['category']})\n"
        
        # Определяем уровень пользователя
        level = await get_user_level(user["points"])
        
        text += f"\nТвой текущий уровень: {level} ⭐"
        
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка при показе достижений: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для приглашения друга
@dp.message(F.text == "👥 Пригласить друга")
async def invite_friend(message: Message):
    user_id = message.from_user.id
    
    # Создаем уникальную ссылку приглашения
    invite_link = await generate_referral_link(user_id)
    
    await message.answer(
        "📱 Пригласи друга и получи дополнительные очки!\n\n"
        f"Твоя уникальная ссылка приглашения:\n{invite_link}\n\n"
        "За каждого приглашенного друга ты получишь +20 очков, когда он выполнит свой первый челлендж!"
    )

# Обработчик для поддержки
@dp.message(F.text == "📞 Поддержка")
async def contact_support(message: Message):
    await message.answer(
        "📞 Поддержка\n\n"
        "По всем вопросам обращайся к разработчику: @AserAbiken\n\n"
        "Sparkaph - приложение для личностного роста через челленджи. "
        "Выполняй задания, получай очки и становись лучше каждый день!"
    )

# Призы для колеса фортуны
FORTUNE_PRIZES = [
    {"type": "points", "value": 10, "text": "10 очков"},
    {"type": "points", "value": 20, "text": "20 очков"},
    {"type": "points", "value": 50, "text": "50 очков"},
    {"type": "bonus", "value": "double_points", "text": "Двойные очки на следующий челлендж"},
    {"type": "bonus", "value": "skip_review", "text": "Автоматическое одобрение следующего челленджа"},
    {"type": "bonus", "value": "extra_challenge", "text": "Дополнительный челлендж"}
]

# Обработчик колеса фортуны
@dp.message(F.text == "🎡 Колесо фортуны")
async def fortune_wheel(message: Message):
    try:
        user_id = message.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            await message.answer("Сначала зарегистрируйся через /start")
            return
        
        # Проверяем, когда пользователь последний раз крутил колесо
        last_spin = user.get("last_fortune_spin")
        if last_spin:
            time_since_last_spin = datetime.now(UTC) - last_spin
            if time_since_last_spin.total_seconds() < 24 * 3600:  # 24 часа
                hours_left = int((24 * 3600 - time_since_last_spin.total_seconds()) / 3600)
                await message.answer(
                    f"⏳ Подождите еще {hours_left} часов перед следующим вращением колеса.\n"
                    "Колесо фортуны можно крутить раз в сутки!"
                )
                return
        
        # Создаем клавиатуру с кнопкой для вращения
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎡 Крутить колесо", callback_data="spin_wheel")]
            ]
        )
        
        await message.answer(
            "🎡 Колесо фортуны\n\n"
            "Крутите колесо раз в сутки и получайте призы:\n"
            "• Очки (10, 20, 50)\n"
            "• Двойные очки на следующий челлендж\n"
            "• Автоматическое одобрение\n"
            "• Дополнительный челлендж\n\n"
            "Готовы попробовать удачу?",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка в колесе фортуны: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик вращения колеса
@dp.callback_query(F.data == "spin_wheel")
async def spin_wheel(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            await callback.answer("Сначала зарегистрируйся через /start")
            return
        
        # Выбираем случайный приз
        prize = random.choice(FORTUNE_PRIZES)
        
        # Обновляем время последнего вращения
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_fortune_spin": datetime.now(UTC)}}
        )
        
        # Применяем приз
        if prize["type"] == "points":
            await db.users.update_one(
                {"user_id": user_id},
                {"$inc": {"points": prize["value"]}}
            )
            await callback.message.edit_text(
                f"🎉 Поздравляем! Вы выиграли {prize['text']}!\n\n"
                f"Ваш баланс обновлен."
            )
        elif prize["type"] == "bonus":
            if prize["value"] == "double_points":
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"next_challenge_double_points": True}}
                )
                await callback.message.edit_text(
                    f"🎉 Поздравляем! Вы выиграли {prize['text']}!\n\n"
                    "Ваш следующий челлендж будет оцениваться в двойном размере."
                )
            elif prize["value"] == "skip_review":
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"next_challenge_auto_approve": True}}
                )
                await callback.message.edit_text(
                    f"🎉 Поздравляем! Вы выиграли {prize['text']}!\n\n"
                    "Ваш следующий челлендж будет автоматически одобрен."
                )
            elif prize["value"] == "extra_challenge":
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"extra_challenge_available": True}}
                )
                await callback.message.edit_text(
                    f"🎉 Поздравляем! Вы выиграли {prize['text']}!\n\n"
                    "Вы можете выполнить дополнительный челлендж сегодня."
                )
        
    except Exception as e:
        logger.error(f"Ошибка при вращении колеса: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик генератора обложек
@dp.message(F.text == "🎨 Генератор обложек")
async def cover_generator(message: Message):
    try:
        user_id = message.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            await message.answer("Сначала зарегистрируйся через /start")
            return
        
        # Получаем последние выполненные челленджи пользователя
        completed_challenges = user.get("completed_challenges", [])
        if not completed_challenges:
            await message.answer(
                "У вас пока нет выполненных челленджей.\n"
                "Выполните хотя бы один челлендж, чтобы создать обложку!"
            )
            return
        
        # Получаем последние 5 выполненных челленджей
        recent_submissions = await db.submissions.find({
            "user_id": user_id,
            "status": "approved",
            "media_type": {"$in": ["photo", "video"]}
        }).sort("submitted_at", -1).limit(5).to_list(length=None)
        
        if not recent_submissions:
            await message.answer(
                "У вас пока нет медиа-контента для создания обложки.\n"
                "Выполните челлендж с фото или видео!"
            )
            return
        
        # Создаем клавиатуру с выбором медиа
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for submission in recent_submissions:
            challenge = await db.challenges.find_one({"_id": submission["challenge_id"]})
            if challenge:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"📸 {challenge['text'][:30]}...",
                        callback_data=f"create_cover_{submission['_id']}"
                    )
                ])
        
        await message.answer(
            "🎨 Генератор обложек\n\n"
            "Выберите медиа для создания обложки:\n"
            "• Для TikTok (9:16)\n"
            "• Для Instagram Stories (9:16)\n"
            "• Для Instagram Posts (1:1)\n\n"
            "Выберите медиа из списка ниже:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка в генераторе обложек: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик создания обложки
@dp.callback_query(F.data.startswith("create_cover_"))
async def create_cover(callback: CallbackQuery):
    try:
        submission_id = callback.data.split("_")[2]
        user_id = callback.from_user.id
        
        # Получаем информацию о submission
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await callback.answer("Медиа не найдено")
            return
        
        # Создаем клавиатуру с выбором формата
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="TikTok (9:16)", callback_data=f"cover_tiktok_{submission_id}")],
                [InlineKeyboardButton(text="Instagram Stories (9:16)", callback_data=f"cover_insta_story_{submission_id}")],
                [InlineKeyboardButton(text="Instagram Post (1:1)", callback_data=f"cover_insta_post_{submission_id}")]
            ]
        )
        
        await callback.message.edit_text(
            "Выберите формат обложки:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании обложки: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Функция для генерации обложки
async def generate_cover(submission: Dict, format_type: str) -> Optional[bytes]:
    try:
        if not submission.get("file_content"):
            return None
            
        # Декодируем base64 в байты
        image_bytes = base64.b64decode(submission["file_content"])
        image = Image.open(io.BytesIO(image_bytes))
        
        # Определяем размеры для разных форматов
        if format_type == "tiktok" or format_type == "insta_story":
            # 9:16 формат (1080x1920)
            target_width = 1080
            target_height = 1920
        else:  # insta_post
            # 1:1 формат (1080x1080)
            target_width = 1080
            target_height = 1080
        
        # Изменяем размер изображения, сохраняя пропорции
        image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Создаем новое изображение с нужным размером и белым фоном
        new_image = Image.new("RGB", (target_width, target_height), "white")
        
        # Вычисляем позицию для центрирования
        x = (target_width - image.width) // 2
        y = (target_height - image.height) // 2
        
        # Вставляем изображение
        new_image.paste(image, (x, y))
        
        # Сохраняем в байты
        output = io.BytesIO()
        new_image.save(output, format="JPEG", quality=95)
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Ошибка при генерации обложки: {e}")
        return None

# Обработчик выбора формата обложки
@dp.callback_query(F.data.startswith("cover_"))
async def process_cover_format(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        format_type = parts[1]
        submission_id = parts[2]
        
        # Получаем информацию о submission
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await callback.answer("Медиа не найдено")
            return
        
        # Генерируем обложку
        cover_bytes = await generate_cover(submission, format_type)
        if not cover_bytes:
            await callback.message.edit_text(
                "❌ Не удалось сгенерировать обложку.\n"
                "Пожалуйста, попробуйте другое изображение."
            )
            return
        
        # Отправляем обложку
        await callback.message.answer_photo(
            photo=cover_bytes,
            caption="🎨 Ваша обложка готова!\n\n"
                   "Вы можете сохранить её и использовать для своих постов."
        )
        
        # Удаляем предыдущее сообщение с выбором формата
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке формата обложки: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Инициализация базы данных
async def init_db():
    try:
        # Создаем индексы для коллекции users
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("username")
        await db.users.create_index("points")
        await db.users.create_index("last_activity")
        await db.users.create_index("last_fortune_spin")
        
        # Создаем индексы для коллекции submissions
        await db.submissions.create_index("user_id")
        await db.submissions.create_index("challenge_id")
        await db.submissions.create_index("status")
        await db.submissions.create_index("submitted_at")
        await db.submissions.create_index("media_type")
        
        # Создаем индексы для коллекции challenges
        await db.challenges.create_index("category_id")
        await db.challenges.create_index("status")
        await db.challenges.create_index("taken_by")
        
        # Создаем индексы для коллекции categories
        await db.categories.create_index("name", unique=True)
        
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise

# Основная функция
async def main():
    try:
        logger.info("Запуск пользовательского бота")
        # Инициализируем базу данных
        await init_db()
        # Запускаем планировщик напоминаний
        asyncio.create_task(reminder_scheduler())
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка в main: {e}")
        raise

# Функция для отправки ежедневного напоминания
async def send_daily_reminder(user_id: int):
    try:
        streak, bonus = await update_streak(user_id)
        if bonus > 0:
            await bot.send_message(
                user_id,
                f"🎁 Ежедневный бонус!\n\n"
                f"Твой streak: {streak} дней 🔥\n"
                f"Получено очков: +{bonus}\n\n"
                f"Заходи каждый день, чтобы увеличить streak и получать больше очков!"
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке ежедневного напоминания: {e}")

# Константы для уведомлений
NOTIFICATION_TYPES = {
    "challenge_reminder": "🔔 Напоминание о челлендже",
    "streak_reminder": "🔥 Не прерывай свой streak!",
    "level_up": "🎯 Новый уровень!",
    "achievement": "🏆 Новое достижение!",
    "referral": "👥 Друг присоединился!",
    "daily_bonus": "🎁 Ежедневный бонус"
}

# Функция для отправки уведомления
async def send_notification(user_id: int, notification_type: str, message: str):
    try:
        # Проверяем настройки уведомлений пользователя
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            return
        
        # Если пользователь отключил уведомления, не отправляем
        if user.get("notifications_disabled", False):
            return
        
        # Отправляем уведомление
        await bot.send_message(
            user_id,
            f"{NOTIFICATION_TYPES.get(notification_type, '📢')} {message}"
        )
        
        # Логируем отправку уведомления
        await db.notifications.insert_one({
            "user_id": user_id,
            "type": notification_type,
            "message": message,
            "sent_at": datetime.now(UTC)
        })
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")

# Функция для отправки напоминания о челлендже
async def send_challenge_reminder(user_id: int):
    try:
        user = await db.users.find_one({"user_id": user_id})
        if not user or not user.get("current_challenge"):
            return
        
        challenge = await db.challenges.find_one({"_id": user["current_challenge"]})
        if not challenge:
            return
        
        # Проверяем, когда был взят челлендж
        challenge_started_at = user.get("challenge_started_at")
        if not challenge_started_at:
            return
        
        # Рассчитываем, сколько времени прошло
        time_passed = (datetime.now(UTC) - challenge_started_at).total_seconds() / 3600
        
        # Отправляем напоминания в зависимости от времени
        if 5.9 <= time_passed <= 6.1 and not user.get("first_reminder_sent"):
            await send_notification(
                user_id,
                "challenge_reminder",
                f"Не забыл выполнить челлендж '{challenge['text']}'? Осталось 6 часов!"
            )
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"first_reminder_sent": True}}
            )
        elif 9.9 <= time_passed <= 10.1 and not user.get("second_reminder_sent"):
            await send_notification(
                user_id,
                "challenge_reminder",
                f"Срочно! Осталось 2 часа на выполнение челленджа '{challenge['text']}'!"
            )
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"second_reminder_sent": True}}
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания о челлендже: {e}")

# Функция для отправки напоминания о streak
async def send_streak_reminder(user_id: int):
    try:
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            return
        
        last_daily = user.get("last_daily")
        if not last_daily:
            return
        
        # Проверяем, прошло ли 23 часа с последнего входа
        time_diff = datetime.now(UTC) - last_daily
        if 23 <= time_diff.total_seconds() / 3600 <= 24:
            streak = user.get("streak", 0)
            if streak > 0:
                await send_notification(
                    user_id,
                    "streak_reminder",
                    f"Не прерывай свой streak в {streak} дней! Зайди в бот в течение часа."
                )
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания о streak: {e}")

# Обновляем планировщик напоминаний
async def reminder_scheduler():
    while True:
        try:
            # Получаем всех пользователей
            users = await db.users.find().to_list(length=None)
            for user in users:
                # Проверяем ежедневный бонус
                last_daily = user.get("last_daily")
                if last_daily:
                    time_diff = datetime.now(UTC) - last_daily
                    if time_diff.days >= 1:
                        await send_daily_reminder(user["user_id"])
                
                # Проверяем напоминания о челленджах
                await send_challenge_reminder(user["user_id"])
                
                # Проверяем напоминания о streak
                await send_streak_reminder(user["user_id"])
            
            # Ждем 5 минут перед следующей проверкой
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Ошибка в планировщике напоминаний: {e}")
            await asyncio.sleep(60)

# Добавляем обработчик для управления уведомлениями
@dp.message(F.text == "🔔 Уведомления")
async def manage_notifications(message: Message):
    try:
        user_id = message.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            return
        
        notifications_disabled = user.get("notifications_disabled", False)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔕 Отключить уведомления" if not notifications_disabled else "🔔 Включить уведомления",
                        callback_data="toggle_notifications"
                    )
                ]
            ]
        )
        
        status = "включены" if not notifications_disabled else "отключены"
        await message.answer(
            f"🔔 Настройки уведомлений\n\n"
            f"Сейчас уведомления {status}.\n\n"
            f"Вы можете получать уведомления о:\n"
            f"• Напоминания о челленджах\n"
            f"• Ежедневные бонусы\n"
            f"• Новые достижения\n"
            f"• Уровни и очки\n"
            f"• Рефералы",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при управлении уведомлениями: {e}")

# Обработчик для переключения уведомлений
@dp.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            return
        
        current_status = user.get("notifications_disabled", False)
        new_status = not current_status
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"notifications_disabled": new_status}}
        )
        
        status = "включены" if not new_status else "отключены"
        await callback.message.edit_text(
            f"🔔 Настройки уведомлений\n\n"
            f"Уведомления {status}.\n\n"
            f"Вы можете получать уведомления о:\n"
            f"• Напоминания о челленджах\n"
            f"• Ежедневные бонусы\n"
            f"• Новые достижения\n"
            f"• Уровни и очки\n"
            f"• Рефералы"
        )
        
        await callback.answer(f"Уведомления {status}")
    except Exception as e:
        logger.error(f"Ошибка при переключении уведомлений: {e}")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Не удалось запустить бота: {e}")
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}") 