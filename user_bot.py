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
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
import io
from models import User
from pymongo import MongoClient
from achievements import achievement_system
from social_media import social_media_manager
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from security import SecuritySystem
from notifications import NotificationSystem
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import logging
import asyncio
from datetime import datetime, UTC
from motor.motor_asyncio import AsyncIOMotorClient
from achievements import AchievementSystem, Achievement
import aiohttp.web

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

# Добавляем простой healthcheck сервер
async def setup_healthcheck():
    app = aiohttp.web.Application()
    
    async def health_handler(request):
        return aiohttp.web.Response(text='OK', status=200)
    
    app.router.add_get('/health', health_handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Healthcheck сервер запущен на 0.0.0.0:8080/health")

# Инициализация бота и диспетчера
try:
    USER_BOT_TOKEN = os.getenv("USER_BOT_TOKEN")
    if not USER_BOT_TOKEN:
        raise ValueError("USER_BOT_TOKEN отсутствует в .env файле")
    
    bot = Bot(token=USER_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
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
        return self.data

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
    waiting_for_social_link = State()

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
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎯 Челленджи"), KeyboardButton(text="📊 Мой рейтинг")],
                [KeyboardButton(text="✅ Мои достижения"), KeyboardButton(text="👥 Пригласить друга")],
                [KeyboardButton(text="📞 Поддержка")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(welcome_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(lambda c: c.data.startswith("gender_"))
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

@dp.callback_query(lambda c: c.data.startswith("age_"))
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
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Челленджи")],
            [KeyboardButton(text="📊 Мой рейтинг"), KeyboardButton(text="✅ Мои достижения")],
            [KeyboardButton(text="👥 Пригласить друга"), KeyboardButton(text="📞 Поддержка")],
            [KeyboardButton(text="🎡 Колесо фортуны"), KeyboardButton(text="🎨 Генератор обложек")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик перехода в меню челленджей
@dp.message(lambda m: m.text == "🎯 Челленджи")
async def show_challenge_categories(message: Message, state: FSMContext):
    try:
        # Получаем все активные категории
        categories = await db.categories.find({"status": "active"}).to_list(length=None)
        
        if not categories:
            await message.answer("К сожалению, сейчас нет доступных категорий челленджей.")
            return
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        for category in categories:
            keyboard.add(InlineKeyboardButton(
                text=category["name"],
                callback_data=f"category_{category['_id']}"
            ))
        
        await message.answer(
            "Выбери категорию челленджа:",
            reply_markup=keyboard
        )
        await state.set_state(UserStates.selecting_category)
        
        except Exception as e:
        logger.error(f"Ошибка при показе категорий челленджей: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

def get_challenge_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Отправить фото или видео")],
            [KeyboardButton(text="🚫 Пропустить челлендж")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик выбора категории
@dp.callback_query(lambda c: c.data.startswith("category_"))
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
@dp.message(lambda m: m.text == "📸 Отправить фото или видео")
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
@dp.message(lambda m: m.text == "🚫 Пропустить челлендж")
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
@dp.message(lambda m: m.text == "🏠 Главное меню")
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
            "Ожидай уведомления. Ты можешь посмотреть свой прогресс в меню (📊 Мой рейтинг, ✅ Мои достижения).",
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
    """Обработчик отправки выполнения челленджа"""
    try:
        user = await db.users.find_one({"user_id": message.from_user.id})
        if not user:
            await message.answer("Вы еще не зарегистрированы. Используйте /start для регистрации.")
            return
        
        # Получаем данные о текущем челлендже
        challenge_id = user.get("current_challenge")
        if not challenge_id:
            await message.answer("У вас нет активного челленджа.")
            return
        
        challenge = await db.challenges.find_one({"_id": ObjectId(challenge_id)})
        if not challenge:
            await message.answer("Челлендж не найден.")
            return
        
        # Сохраняем выполнение
        submission = {
            "user_id": message.from_user.id,
            "challenge_id": challenge_id,
            "submitted_at": datetime.utcnow(),
            "status": "pending"
        }
        
        # Если есть медиа, сохраняем его
        if message.photo:
            submission["media_type"] = "photo"
            submission["media_id"] = message.photo[-1].file_id
        elif message.video:
            submission["media_type"] = "video"
            submission["media_id"] = message.video.file_id
        
        # Сохраняем выполнение
        await db.submissions.insert_one(submission)
        
        # Обновляем данные пользователя
        await db.users.update_one(
            {"user_id": message.from_user.id},
            {
                "$set": {"current_challenge": None},
                "$push": {"completed_challenges": challenge_id}
            }
        )
        
        # Проверяем и награждаем достижениями
        await check_and_award_achievements(message.from_user.id)
        
        # Обновляем серию дней
        await update_streak(message.from_user.id)
        
        await message.answer(
            "✅ Ваше выполнение челленджа принято!\n"
            "Оно будет проверено модераторами в ближайшее время."
        )
        
        # Возвращаем в главное меню
        await state.clear()
        await message.answer("Выберите действие:", reply_markup=get_main_menu())
        
    except Exception as e:
        logger.error(f"Ошибка при обработке выполнения челленджа: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

# Обработчик рейтинга
@dp.message(lambda m: m.text == "📊 Мой рейтинг")
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
@dp.message(lambda m: m.text == "✅ Мои достижения")
async def show_achievements(message: Message):
    """Показать достижения пользователя"""
    try:
        user = await db.users.find_one({"user_id": message.from_user.id})
        
        if not user:
            await message.answer("Вы еще не зарегистрированы. Используйте /start для регистрации.")
            return
        
        # Получаем достижения пользователя
        user_achievements = achievement_system.get_user_achievements(User(**user))
        
        # Форматируем список достижений
        achievements_text = achievement_system.format_achievements_list(user_achievements)
        
        # Добавляем информацию о прогрессе
        total_achievements = len(achievement_system.get_all_achievements())
        earned_achievements = len(user_achievements)
        progress = (earned_achievements / total_achievements) * 100
        
        header = f"🏆 Ваши достижения ({earned_achievements}/{total_achievements})\n"
        progress_bar = f"Прогресс: {'█' * int(progress/10)}{'░' * (10 - int(progress/10))} {progress:.1f}%\n\n"
        
        await message.answer(header + progress_bar + achievements_text)
        
    except Exception as e:
        logger.error(f"Ошибка при показе достижений: {e}")
        await message.answer("Произошла ошибка при загрузке достижений. Попробуйте позже.")

async def check_and_award_achievements(user_id: int):
    """Проверяет и награждает пользователя достижениями"""
    try:
        user_data = await db.users.find_one({"user_id": user_id})
        if not user_data:
            return
        
        user = User(**user_data)
        new_achievements = await achievement_system.check_achievements(user)
        
        if new_achievements:
            # Обновляем данные пользователя
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "achievements": user.achievements,
                        "points": user.points
                    }
                }
            )
            
            # Отправляем уведомление о новых достижениях
            achievements_text = "\n\n".join(
                f"🏆 {achievement.name}\n{achievement.description}\n+{achievement.points} очков"
                for achievement in new_achievements
            )
            
            await bot.send_message(
                user_id,
                f"🎉 Поздравляем! Вы получили новые достижения:\n\n{achievements_text}"
            )
    
    except Exception as e:
        logger.error(f"Ошибка при проверке достижений: {e}")

# Обработчик для приглашения друга
@dp.message(lambda m: m.text == "👥 Пригласить друга")
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
@dp.message(lambda m: m.text == "📞 Поддержка")
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
@dp.message(lambda m: m.text == "🎡 Колесо фортуны")
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
@dp.callback_query(lambda c: c.data == "spin_wheel")
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
@dp.message(lambda m: m.text == "🎨 Генератор обложек")
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
@dp.callback_query(lambda c: c.data.startswith("create_cover_"))
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
@dp.callback_query(lambda c: c.data.startswith("cover_"))
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
        # Запускаем healthcheck сервер
        await setup_healthcheck()
        # Инициализируем базу данных
        await init_db()
        # Запускаем менеджер сессий
        session_manager.start()
        # Запускаем планировщик напоминаний
        asyncio.create_task(reminder_scheduler())
        try:
            await dp.start_polling(bot)
        finally:
            # Закрываем все сессии при завершении
            await session_manager.stop()
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
@dp.message(lambda m: m.text == "🔔 Уведомления")
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
@dp.callback_query(lambda c: c.data == "toggle_notifications")
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

@dp.message(Command("send_link"))
async def send_social_link(message: types.Message):
    user_id = message.from_user.id
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    await message.answer(
        "Если ты выложил видео/фото с челленджем в TikTok или Instagram, пришли сюда ссылку на свой пост!\n\n"
        "Это поможет нам продвигать Sparkaph и даст тебе шанс попасть в топ!\n\n"
        "Просто отправь ссылку одним сообщением."
    )
    await state.set_state("waiting_for_social_link")

@dp.message(UserStates.waiting_for_social_link)
async def save_social_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    link = message.text.strip()
    # Простейшая валидация
    if not (link.startswith("http://") or link.startswith("https://")):
        await message.answer("Похоже, это не ссылка. Попробуй ещё раз!")
        return
    await db.users.update_one({"user_id": user_id}, {"$push": {"social_links": link}})
    await message.answer("Спасибо! Ссылка сохранена. Ты молодец!")
    await state.clear()

@dp.message(lambda m: m.text == "📱 Поделиться в соцсетях")
async def share_to_social_media(message: Message):
    """Показать меню для публикации в социальных сетях"""
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
                "Выполните хотя бы один челлендж, чтобы поделиться им!"
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
                "У вас пока нет медиа-контента для публикации.\n"
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
                        callback_data=f"share_media_{submission['_id']}"
                    )
                ])
        
        await message.answer(
            "📱 Поделиться в соцсетях\n\n"
            "Выберите медиа для публикации:\n"
            "• TikTok\n"
            "• Instagram Post\n"
            "• Instagram Story\n\n"
            "Выберите медиа из списка ниже:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при показе меню соцсетей: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(lambda c: c.data.startswith("share_media_"))
async def handle_share_media(callback: CallbackQuery):
    """Обработчик выбора медиа для публикации"""
    try:
        submission_id = callback.data.split("_")[2]
        user_id = callback.from_user.id
        
        # Получаем информацию о submission
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await callback.answer("Медиа не найдено")
            return
        
        # Создаем клавиатуру с выбором платформы
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="TikTok", callback_data=f"platform_tiktok_{submission_id}")],
                [InlineKeyboardButton(text="Instagram Post", callback_data=f"platform_instagram_post_{submission_id}")],
                [InlineKeyboardButton(text="Instagram Story", callback_data=f"platform_instagram_story_{submission_id}")]
            ]
        )
        
        await callback.message.edit_text(
            "Выберите платформу для публикации:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при выборе медиа: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(lambda c: c.data.startswith("platform_"))
async def handle_platform_selection(callback: CallbackQuery):
    """Обработчик выбора платформы для публикации"""
    try:
        parts = callback.data.split("_")
        platform = parts[1]
        post_type = parts[2] if len(parts) > 2 else None
        submission_id = parts[-1]
        
        # Получаем информацию о submission
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await callback.answer("Медиа не найдено")
            return
        
        # Получаем информацию о челлендже
        challenge = await db.challenges.find_one({"_id": submission["challenge_id"]})
        if not challenge:
            await callback.answer("Челлендж не найден")
            return
        
        # Создаем временный файл с медиа
        temp_dir = "temp_media"
        os.makedirs(temp_dir, exist_ok=True)
        
        media_path = os.path.join(temp_dir, f"{submission_id}.{'mp4' if submission['media_type'] == 'video' else 'jpg'}")
        
        # Декодируем и сохраняем медиа
        if submission.get("file_content"):
            with open(media_path, "wb") as f:
                f.write(base64.b64decode(submission["file_content"]))
        
        # Формируем подпись
        caption = f"🎯 Челлендж: {challenge['text']}\n\n"
        caption += f"💪 Выполнил челлендж в @Sparkaph\n"
        caption += "#Sparkaph #Челленджи #ЛичностныйРост"
        
        # Публикуем в зависимости от платформы
        if platform == "tiktok":
            result = await social_media_manager.post_to_tiktok(
                video_path=media_path,
                caption=caption,
                user_id=callback.from_user.id
            )
        elif platform == "instagram":
            result = await social_media_manager.post_to_instagram(
                media_path=media_path,
                caption=caption,
                user_id=callback.from_user.id,
                is_story=(post_type == "story")
            )
        else:
            await callback.answer("Неподдерживаемая платформа")
            return
        
        # Удаляем временный файл
        try:
            os.remove(media_path)
        except:
            pass
        
        if result:
            # Сохраняем информацию о публикации
            await db.social_posts.insert_one({
                "user_id": callback.from_user.id,
                "submission_id": submission_id,
                "platform": platform,
                "post_type": post_type,
                "post_id": result.get("id") or result.get("video_id"),
                "published_at": datetime.now(UTC)
            })
            
            # Начисляем бонусные очки
            await db.users.update_one(
                {"user_id": callback.from_user.id},
                {"$inc": {"points": 50}}  # 50 очков за публикацию
            )
            
            await callback.message.edit_text(
                "✅ Публикация успешно размещена!\n\n"
                "Вы получили 50 бонусных очков за публикацию.\n"
                "Продолжайте делиться своими достижениями!"
            )
        else:
            await callback.message.edit_text(
                "❌ Не удалось опубликовать контент.\n"
                "Пожалуйста, попробуйте позже или выберите другое медиа."
            )
        
    except Exception as e:
        logger.error(f"Ошибка при публикации в соцсети: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Инициализация системы достижений
achievement_system = AchievementSystem(db)

# Добавляем новые состояния
class AchievementStates(StatesGroup):
    viewing_achievements = State()
    viewing_progress = State()

# Добавляем новые команды
@dp.message_handler(commands=['achievements'])
async def show_achievements(message: types.Message):
    """Показать достижения пользователя"""
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью команды /start")
        return
    
    # Получаем достижения пользователя
    user_achievements = await achievement_system.get_user_achievements(user)
    
    # Форматируем список достижений
    text = "🏆 Ваши достижения:\n\n"
    text += achievement_system.format_achievements_list(user_achievements)
    
    # Добавляем кнопки
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📊 Прогресс", callback_data="achievement_progress"))
    keyboard.add(InlineKeyboardButton("🎯 Доступные", callback_data="available_achievements"))
    
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "achievement_progress")
async def show_progress(callback_query: types.CallbackQuery):
    """Показать прогресс достижений"""
    user = await get_user(callback_query.from_user.id)
    if not user:
        await callback_query.answer("Сначала зарегистрируйтесь")
        return
    
    # Получаем доступные достижения
    available_achievements = await achievement_system.get_available_achievements(user)
    
    if not available_achievements:
        await callback_query.answer("У вас нет доступных достижений")
        return
    
    # Форматируем прогресс
    text = "📊 Прогресс достижений:\n\n"
    for achievement in available_achievements:
        progress = await achievement_system.get_achievement_progress(user, achievement)
        text += f"{achievement.icon} {achievement.name}\n"
        for key, value in progress.items():
            text += f"Прогресс: {value['current']}/{value['required']} ({value['percentage']:.0f}%)\n"
        text += "\n"
    
    await callback_query.message.edit_text(text, reply_markup=callback_query.message.reply_markup)

@dp.callback_query_handler(lambda c: c.data == "available_achievements")
async def show_available(callback_query: types.CallbackQuery):
    """Показать доступные достижения"""
    user = await get_user(callback_query.from_user.id)
    if not user:
        await callback_query.answer("Сначала зарегистрируйтесь")
        return
    
    # Получаем доступные достижения
    available_achievements = await achievement_system.get_available_achievements(user)
    
    if not available_achievements:
        await callback_query.answer("У вас нет доступных достижений")
        return
    
    # Форматируем список
    text = "🎯 Доступные достижения:\n\n"
    text += achievement_system.format_achievements_list(available_achievements)
    
    await callback_query.message.edit_text(text, reply_markup=callback_query.message.reply_markup)

# Обновляем существующие функции для интеграции с системой достижений

async def complete_challenge(user_id: int, challenge_id: str):
    """Обновляем функцию завершения челленджа"""
    user = await get_user(user_id)
    if not user:
        return False
    
    # Добавляем челлендж в список выполненных
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$push": {
                "completed_challenges": {
                    "challenge_id": challenge_id,
                    "completed_at": datetime.now(UTC)
                }
            }
        }
    )
    
    # Проверяем достижения
    new_achievements = await achievement_system.check_achievements(user)
    
    # Выдаем новые достижения
    for achievement in new_achievements:
        await achievement_system.award_achievement(user_id, achievement)
        
        # Отправляем уведомление о новом достижении
        bot = Bot.get_current()
        await bot.send_message(
            user_id,
            f"🎉 Поздравляем! Вы получили новое достижение:\n\n"
            f"{achievement.icon} {achievement.name}\n"
            f"📝 {achievement.description}\n"
            f"⭐️ +{achievement.points} очков"
        )
    
    return True

async def update_streak(user_id: int):
    """Обновляем функцию обновления серии"""
    user = await get_user(user_id)
    if not user:
        return False
    
    # Обновляем серию
    await db.users.update_one(
        {"user_id": user_id},
        {"$inc": {"streak": 1}}
    )
    
    # Проверяем достижения
    new_achievements = await achievement_system.check_achievements(user)
    
    # Выдаем новые достижения
    for achievement in new_achievements:
        await achievement_system.award_achievement(user_id, achievement)
        
        # Отправляем уведомление о новом достижении
        bot = Bot.get_current()
        await bot.send_message(
            user_id,
            f"🎉 Поздравляем! Вы получили новое достижение:\n\n"
            f"{achievement.icon} {achievement.name}\n"
            f"📝 {achievement.description}\n"
            f"⭐️ +{achievement.points} очков"
        )
    
    return True

async def add_referral(user_id: int, referral_id: int):
    """Обновляем функцию добавления реферала"""
    user = await get_user(user_id)
    if not user:
        return False
    
    # Добавляем реферала
    await db.users.update_one(
        {"user_id": user_id},
        {"$push": {"referrals": referral_id}}
    )
    
    # Проверяем достижения
    new_achievements = await achievement_system.check_achievements(user)
    
    # Выдаем новые достижения
    for achievement in new_achievements:
        await achievement_system.award_achievement(user_id, achievement)
        
        # Отправляем уведомление о новом достижении
        bot = Bot.get_current()
        await bot.send_message(
            user_id,
            f"🎉 Поздравляем! Вы получили новое достижение:\n\n"
            f"{achievement.icon} {achievement.name}\n"
            f"📝 {achievement.description}\n"
            f"⭐️ +{achievement.points} очков"
        )
    
    return True

async def add_social_share(user_id: int, challenge_id: str):
    """Обновляем функцию добавления шера в соцсети"""
    user = await get_user(user_id)
    if not user:
        return False
    
    # Добавляем шеер
    await db.users.update_one(
        {"user_id": user_id},
        {"$push": {"social_shares": challenge_id}}
    )
    
    # Проверяем достижения
    new_achievements = await achievement_system.check_achievements(user)
    
    # Выдаем новые достижения
    for achievement in new_achievements:
        await achievement_system.award_achievement(user_id, achievement)
        
        # Отправляем уведомление о новом достижении
        bot = Bot.get_current()
        await bot.send_message(
            user_id,
            f"🎉 Поздравляем! Вы получили новое достижение:\n\n"
            f"{achievement.icon} {achievement.name}\n"
            f"📝 {achievement.description}\n"
            f"⭐️ +{achievement.points} очков"
        )
    
    return True

async def update_level(user_id: int, new_level: int):
    """Обновляем функцию обновления уровня"""
    user = await get_user(user_id)
    if not user:
        return False
    
    # Обновляем уровень
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"level": new_level}}
    )
    
    # Проверяем достижения
    new_achievements = await achievement_system.check_achievements(user)
    
    # Выдаем новые достижения
    for achievement in new_achievements:
        await achievement_system.award_achievement(user_id, achievement)
        
        # Отправляем уведомление о новом достижении
        bot = Bot.get_current()
        await bot.send_message(
            user_id,
            f"🎉 Поздравляем! Вы получили новое достижение:\n\n"
            f"{achievement.icon} {achievement.name}\n"
            f"📝 {achievement.description}\n"
            f"⭐️ +{achievement.points} очков"
        )
    
    return True

# Добавляем периодическую очистку истекших достижений
async def cleanup_achievements():
    """Периодическая очистка истекших достижений"""
    while True:
        await achievement_system.cleanup_expired_achievements()
        await asyncio.sleep(3600)  # Проверяем каждый час

# Добавляем запуск очистки при старте бота
if __name__ == '__main__':
    try:
        # Запускаем очистку достижений
        asyncio.create_task(cleanup_achievements())
        # Запускаем бота
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise

def register_handlers(dispatcher):
    pass