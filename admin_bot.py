import os
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, Union
from bson import ObjectId
import base64
import tempfile
import ssl
import certifi
import urllib.parse
import dns.resolver
import asyncio

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from cover_generator import cover_generator
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from security import SecuritySystem
from notifications import NotificationSystem
from achievements import AchievementSystem, Achievement, AchievementType, AchievementReward
from notifications import NotificationType
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Глобальные переменные для хранения подключения к БД
db = None
MOCK_DB = False

# Преобразование ADMIN_ID из строки в int
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    logger.info(f"Admin ID установлен: {ADMIN_ID}")
except (ValueError, TypeError) as e:
    ADMIN_ID = 1521413812  # Fallback на ваш ID
    logger.error(f"Ошибка при преобразовании ADMIN_ID, используем значение по умолчанию: {e}")

# Инициализация бота и диспетчера
try:
    bot = Bot(token=os.getenv("ADMIN_BOT_TOKEN"))
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
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
        # Для тестирования админа
        if self.name == "users" and query and query.get("user_id") == ADMIN_ID:
            return {"user_id": ADMIN_ID, "username": "admin", "points": 0}
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

# Функция для создания клиента MongoDB с повторными попытками
async def create_mongodb_client(max_retries=3):
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"Попытка подключения к MongoDB (попытка {retry_count + 1}/{max_retries})...")
            
            # Получаем URI из переменных окружения
            mongodb_uri = os.getenv("MONGODB_URI", "")
            if not mongodb_uri:
                logger.error("MONGODB_URI не найден в .env файле")
                return None

            # Логируем URI (без пароля)
            safe_uri = mongodb_uri.replace(
                mongodb_uri.split('@')[0],
                mongodb_uri.split('@')[0].split(':')[0] + ':***'
            ) if '@' in mongodb_uri else 'mongodb://***:***@host'
            logger.info(f"Попытка подключения к: {safe_uri}")

            # Создаем клиента с минимальными настройками
            client = AsyncIOMotorClient(
                mongodb_uri,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                serverSelectionTimeoutMS=30000,
                retryWrites=True,
                tls=True,  # Используем tls вместо ssl
                tlsAllowInvalidCertificates=True  # Временно разрешаем невалидные сертификаты
            )

            # Проверяем подключение с таймаутом
            try:
                logger.info("Проверка подключения...")
                await asyncio.wait_for(client.admin.command('ping'), timeout=10.0)
                logger.info("Пинг успешен!")
                return client
            except asyncio.TimeoutError:
                logger.error("Таймаут при проверке подключения")
                raise
            except Exception as ping_error:
                logger.error(f"Ошибка при проверке подключения: {ping_error}")
                raise

        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            logger.error(f"Ошибка подключения к MongoDB (попытка {retry_count}/{max_retries})")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            logger.error(f"Описание ошибки: {error_msg}")
            
            if "ServerSelectionTimeoutError" in error_msg:
                logger.error("Проблема с выбором сервера. Проверьте доступность кластера и сетевые настройки.")
            elif "SSL" in error_msg or "TLS" in error_msg:
                logger.error("Проблема с SSL/TLS. Возможно, проблема с сертификатами или настройками безопасности.")
            elif "Authentication failed" in error_msg:
                logger.error("Ошибка аутентификации. Проверьте правильность имени пользователя и пароля.")
            elif "connect" in error_msg.lower():
                logger.error("Проблема с подключением. Проверьте сетевое подключение и брандмауэр.")

            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.info(f"Ожидание {wait_time} секунд перед следующей попыткой...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Все попытки подключения к MongoDB исчерпаны")
                return None

# Асинхронная функция инициализации MongoDB
async def init_mongodb():
    global db, MOCK_DB
    try:
        # Пытаемся создать клиента MongoDB
        logger.info("Начало инициализации MongoDB...")
        mongo_client = await create_mongodb_client()
        
        if mongo_client is None:
            logger.warning("Не удалось подключиться к MongoDB, переключаемся на MOCK_DB")
            MOCK_DB = True
            db = MockDB()
        else:
            db = mongo_client.Sparkaph
            # Проверяем доступ к базе данных
            try:
                collections = await db.list_collection_names()
                logger.info(f"Доступные коллекции: {collections}")
                logger.info("MongoDB клиент успешно инициализирован")
            except Exception as e:
                logger.error(f"Ошибка при проверке коллекций: {e}")
                MOCK_DB = True
                db = MockDB()

    except Exception as e:
        logger.error(f"Критическая ошибка при инициализации MongoDB: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        db = MockDB()
        MOCK_DB = True

# Инициализация систем безопасности и уведомлений
security = SecuritySystem(bot, db)
notifications = NotificationSystem(bot, db)

# Состояния
class AdminStates(StatesGroup):
    waiting_for_category_name = State()
    waiting_for_category_description = State()
    waiting_for_challenge_text = State()
    waiting_for_challenge_description = State()
    waiting_for_challenge_category = State()
    waiting_for_challenge_max_users = State()
    waiting_for_reject_reason = State()  # Ожидание причины отказа
    waiting_for_user_points = State()
    waiting_for_influencer_id = State()
    waiting_for_influencer_category = State()
    waiting_for_challenges_file = State()
    waiting_for_cover_text = State()
    waiting_for_cover_style = State()
    waiting_for_cover_format = State()
    waiting_for_challenge_name = State()
    waiting_for_challenge_points = State()
    waiting_for_influencer_username = State()
    waiting_for_influencer_platform = State()

class AchievementStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_type = State()
    waiting_for_requirements = State()
    waiting_for_rewards = State()
    waiting_for_expires_at = State()
    waiting_for_season = State()
    waiting_for_collection = State()
    waiting_for_event = State()
    waiting_for_special = State()
    waiting_for_hidden = State()
    waiting_for_points = State()
    waiting_for_badge = State()
    waiting_for_title = State()
    waiting_for_bonus = State()
    waiting_for_bonus_duration = State()

# Вспомогательная функция для сохранения ID сообщения и submission_id
async def save_temp_data(state: FSMContext, submission_id: str, message_id: int):
    await state.update_data(submission_id=submission_id, message_id=message_id)

# Middleware для проверки безопасности
@dp.middleware()
async def security_middleware(handler, event, data):
    if isinstance(event, types.Message):
        user_id = event.from_user.id
        
        # Проверка прав администратора
        admin = await db.admins.find_one({"user_id": user_id})
        if not admin:
            await event.answer("У вас нет прав администратора.")
            return
        
        # Проверка rate limit
        allowed, wait_time = await security.check_rate_limit(user_id, "message")
        if not allowed:
            await event.answer(f"Слишком много сообщений. Подождите {wait_time} секунд.")
            return
        
        # Проверка на спам
        if event.text:
            is_safe, reason = await security.check_spam(event.text)
            if not is_safe:
                await security.log_security_event(
                    user_id,
                    "admin_spam_detected",
                    {"text": event.text, "reason": reason}
                )
                await event.answer("Сообщение заблокировано системой безопасности.")
                return
    
    return await handler(event, data)

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: Message):
    try:
        # Проверяем ID
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Попытка доступа к админ-боту: user_id={message.from_user.id}, username={message.from_user.username}")
            await message.answer("У вас нет доступа к админ-панели.")
            return
        
        logger.info(f"Админ вошел в систему: {message.from_user.id} ({message.from_user.username})")
        await message.answer(
            "👋 Добро пожаловать в админ-панель Sparkaph!\n\n"
            "Используйте меню для управления ботом.",
            reply_markup=get_admin_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Клавиатура админ-меню
def get_admin_menu():
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📝 Проверить задания")],
            [types.KeyboardButton(text="📊 Статистика")],
            [types.KeyboardButton(text="📋 Управление категориями")],
            [types.KeyboardButton(text="🎯 Управление челленджами")],
            [types.KeyboardButton(text="👥 Управление пользователями")],
            [types.KeyboardButton(text="👥 Управление инфлюенсерами")],
            [types.KeyboardButton(text="📋 Массовое добавление челленджей")],
            [types.KeyboardButton(text="🎨 Генератор обложек")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик проверки заданий
@dp.message(lambda m: m.text == "📝 Проверить задания")
async def check_submissions(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Получение ожидающих проверки заданий
        submissions = await db.submissions.find({
            "status": "pending"
        }).to_list(length=None)
        
        if not submissions:
            await message.answer("Нет заданий, ожидающих проверки.")
            return
        
        sent_count = 0
        for submission in submissions:
            user = await db.users.find_one({"user_id": submission["user_id"]})
            challenge = await db.challenges.find_one({"_id": submission["challenge_id"]})
            
            if not user or not challenge:
                continue
            
            text = (
                f"📝 Новое задание на проверку:\n\n"
                f"От: @{user['username']} (ID: {user['user_id']})\n"
                f"Челлендж: {challenge['text']}\n"
                f"Ответ: {submission['text']}\n"
                f"Время: {submission['submitted_at'].strftime('%Y-%m-%d %H:%M')}"
            )
            
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="✅ Одобрить",
                            callback_data=f"approve_{submission['_id']}"
                        ),
                        types.InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=f"reject_{submission['_id']}"
                        )
                    ]
                ]
            )
            
            sent = False
            file_content = submission.get("file_content")
            # Отправляем медиафайл или текст
            if submission.get("media") and file_content:
                try:
                    media_type = submission.get("media_type", "")
                    
                    # Сохраняем содержимое файла во временный файл
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{media_type}") as temp_file:
                        temp_file.write(base64.b64decode(file_content))
                        temp_path = temp_file.name
                    
                    logger.info(f"Сохранен временный файл: {temp_path}")
                    
                    try:
                        if "photo" in media_type:
                            # Отправляем как фото
                            with open(temp_path, 'rb') as photo_file:
                                msg = await message.answer_photo(
                                    photo=types.BufferedInputFile(
                                        photo_file.read(),
                                        filename=f"photo.{media_type}"
                                    ),
                                    caption=text,
                                    reply_markup=keyboard
                                )
                            sent = True
                        elif "video" in media_type:
                            # Отправляем как видео
                            with open(temp_path, 'rb') as video_file:
                                msg = await message.answer_video(
                                    video=types.BufferedInputFile(
                                        video_file.read(),
                                        filename=f"video.{media_type}"
                                    ),
                                    caption=text,
                                    reply_markup=keyboard
                                )
                            sent = True
                        else:
                            # Отправляем как документ
                            with open(temp_path, 'rb') as doc_file:
                                msg = await message.answer_document(
                                    document=types.BufferedInputFile(
                                        doc_file.read(),
                                        filename=f"document.{media_type}"
                                    ),
                                    caption=text,
                                    reply_markup=keyboard
                                )
                            sent = True
                    except Exception as e:
                        logger.error(f"Ошибка при отправке файла: {e}")
                        # Если не удалось отправить файл, отправляем текст
                        msg = await message.answer(
                            text + "\n\n⚠️ [Не удалось загрузить медиа из файла]",
                            reply_markup=keyboard
                        )
                        sent = True
                    
                    # Удаляем временный файл
                    try:
                        os.remove(temp_path)
                        logger.info(f"Удален временный файл: {temp_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении временного файла: {e}")
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке файла: {e}")
                    # Если не удалось декодировать файл, пробуем использовать file_id
                    try:
                        media_type = submission.get("media_type", "")
                        media_file_id = submission.get("media")
                        
                        if "photo" in media_type:
                            msg = await message.answer_photo(
                                photo=media_file_id,
                                caption=text,
                                reply_markup=keyboard
                            )
                            sent = True
                        elif "video" in media_type:
                            msg = await message.answer_video(
                                video=media_file_id,
                                caption=text,
                                reply_markup=keyboard
                            )
                            sent = True
                        else:
                            msg = await message.answer_document(
                                document=media_file_id,
                                caption=text,
                                reply_markup=keyboard
                            )
                            sent = True
                    except Exception as e:
                        logger.error(f"Ошибка при отправке медиа по file_id: {e}")
                        # Если все попытки не удались, отправляем текст
                        msg = await message.answer(
                            text + "\n\n⚠️ [Не удалось загрузить медиа. ID медиа: " + str(submission.get("media")) + "]",
                            reply_markup=keyboard
                        )
                        sent = True
            elif submission.get("media"):
                # Если есть только file_id без содержимого
                try:
                    media_type = submission.get("media_type", "")
                    media_file_id = submission.get("media")
                    
                    if "photo" in media_type:
                        msg = await message.answer_photo(
                            photo=media_file_id,
                            caption=text,
                            reply_markup=keyboard
                        )
                        sent = True
                    elif "video" in media_type:
                        msg = await message.answer_video(
                            video=media_file_id,
                            caption=text,
                            reply_markup=keyboard
                        )
                        sent = True
                    else:
                        msg = await message.answer_document(
                            document=media_file_id,
                            caption=text,
                            reply_markup=keyboard
                        )
                        sent = True
                except Exception as e:
                    logger.error(f"Ошибка при отправке медиа: {e}")
                    # Если все попытки с медиа не удались, отправляем как текст с уведомлением
                    msg = await message.answer(
                        text + "\n\n⚠️ [Не удалось загрузить медиа. ID медиа: " + str(media_file_id) + "]",
                        reply_markup=keyboard
                    )
                    sent = True
            else:
                # Если нет медиа, отправляем как обычный текст
                msg = await message.answer(text, reply_markup=keyboard)
                sent = True
            
            if sent:
                sent_count += 1
        
        if sent_count == 0:
            await message.answer("Не удалось загрузить задания на проверку. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка при проверке заданий: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Показ статистики пользователей
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Проверяем режим работы с базой данных
        if MOCK_DB:
            await message.answer("⚠️ База данных недоступна (режим заглушки). Статистика недоступна.")
            return
            
        # Сбор основной статистики
        try:
            # Получаем временные метки для разных периодов
            now = datetime.now(UTC)
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # Общее количество пользователей
            total_users = await db.users.count_documents({})
            
            # Активные пользователи за 24 часа, 7 дней и 30 дней
            active_users_24h = await db.users.count_documents({"last_active": {"$gte": day_ago}})
            active_users_7d = await db.users.count_documents({"last_active": {"$gte": week_ago}})
            active_users_30d = await db.users.count_documents({"last_active": {"$gte": month_ago}})
            
            # Пользователи с неоконченными челленджами
            users_with_challenges = await db.users.count_documents({"current_challenge": {"$ne": None}})
            
            # Процент выполнения челленджей
            total_challenges = await db.challenges.count_documents({})
            completed_challenges = await db.submissions.count_documents({"status": "approved"})
            
            # Статистика категорий
            categories = await db.categories.find().to_list(length=100)
            category_stats = {}
            
            for category in categories:
                cat_id = category["_id"]
                challenges_count = await db.challenges.count_documents({"category_id": cat_id})
                completed_count = await db.submissions.count_documents({
                    "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": cat_id})]},
                    "status": "approved"
                })
                
                category_stats[category["name"]] = {
                    "challenges_count": challenges_count,
                    "completed_count": completed_count
                }
            
            # Статистика по времени ответа на задания
            submissions = await db.submissions.find({"status": "approved", "reviewed_at": {"$exists": True}}).to_list(length=None)
            
            avg_response_time = 0
            if submissions:
                response_times = []
                for submission in submissions:
                    if submission.get("reviewed_at"):
                        response_time = submission["reviewed_at"] - submission["submitted_at"]
                        response_times.append(response_time.total_seconds() / 3600)
                
                if response_times:
                    avg_response_time = sum(response_times) / len(response_times)
            
            # Расчет метрик удержания
            retention_1d = (active_users_24h / total_users * 100) if total_users > 0 else 0
            retention_7d = (active_users_7d / total_users * 100) if total_users > 0 else 0
            retention_30d = (active_users_30d / total_users * 100) if total_users > 0 else 0
            
            # Статистика по пользователям с подпиской на канал
            subscribed_users = await db.users.count_documents({"subscription": True})
            subscription_rate = (subscribed_users / total_users * 100) if total_users > 0 else 0
            
            # Создаем текст отчета
            text = (
                f"📊 **Общая статистика**\n\n"
                f"👥 **Пользователи:**\n"
                f"• Всего: {total_users}\n"
                f"• Активные (24ч): {active_users_24h} ({retention_1d:.1f}%)\n"
                f"• Активные (7д): {active_users_7d} ({retention_7d:.1f}%)\n"
                f"• Активные (30д): {active_users_30d} ({retention_30d:.1f}%)\n"
                f"• С активными челленджами: {users_with_challenges}\n\n"
                
                f"🎯 **Челленджи:**\n"
                f"• Всего: {total_challenges}\n"
                f"• Выполнено: {completed_challenges}\n"
                f"• Процент выполнения: {(completed_challenges / total_challenges * 100) if total_challenges > 0 else 0:.1f}%\n\n"
                
                f"⏱ **Метрики:**\n"
                f"• Среднее время проверки: {avg_response_time:.1f} часов\n"
                f"• Подписались на канал: {subscribed_users} ({subscription_rate:.1f}%)\n"
            )
            
            await message.answer(text)
            
            # Формируем статистику по категориям
            category_text = "📋 **Статистика по категориям:**\n\n"
            for name, data in category_stats.items():
                category_text += f"• {name}: {data['completed_count']} выполнено из {data['challenges_count']} челленджей\n"
            
            await message.answer(category_text)
            
        except Exception as e:
            logger.error(f"Ошибка при сборе статистики: {e}")
            await message.answer(f"Произошла ошибка при сборе статистики: {e}")
            await message.answer("Попробуйте позже или обратитесь к разработчику.")
        
    except Exception as e:
        logger.error(f"Общая ошибка в команде /stats: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчики управления категориями
@dp.message(lambda m: m.text == "📋 Управление категориями")
async def manage_categories(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="➕ Добавить категорию",
                        callback_data="add_category"
                    ),
                    types.InlineKeyboardButton(
                        text="🗑 Удалить категорию",
                        callback_data="delete_category"
                    )
                ]
            ]
        )
        
        categories = await db.categories.find().to_list(length=None)
        text = "📋 Категории:\n\n"
        for category in categories:
            text += f"• {category['name']}\n"
        
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при управлении категориями: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчики управления челленджами
@dp.message(lambda m: m.text == "🎯 Управление челленджами")
async def manage_challenges(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="➕ Добавить челлендж",
                        callback_data="add_challenge"
                    ),
                    types.InlineKeyboardButton(
                        text="🗑 Удалить челлендж",
                        callback_data="delete_challenge"
                    )
                ]
            ]
        )
        
        challenges = await db.challenges.find().to_list(length=None)
        text = "🎯 Челленджи:\n\n"
        for challenge in challenges:
            category = await db.categories.find_one({"_id": challenge["category_id"]})
            if category:
                text += f"• {challenge['text']} ({category['name']})\n"
        
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при управлении челленджами: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчики управления пользователями
@dp.message(lambda m: m.text == "👥 Управление пользователями")
async def manage_users(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Получение топ пользователей
        users = await db.users.find().sort("points", -1).limit(10).to_list(length=None)
        
        text = "👥 Топ пользователей:\n\n"
        for i, user in enumerate(users, 1):
            text += f"{i}. @{user['username']} - {user['points']} очков\n"
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="➕ Выдать очки",
                        callback_data="add_points"
                    ),
                    types.InlineKeyboardButton(
                        text="➖ Снять очки",
                        callback_data="remove_points"
                    )
                ]
            ]
        )
        
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при управлении пользователями: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчики callback-запросов
@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_submission(callback: CallbackQuery):
    try:
        if callback.from_user.id != ADMIN_ID:
            return
        
        submission_id = callback.data.split("_")[1]
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        
        if not submission:
            await callback.answer("Задание не найдено.")
            return
        
        # Обновление статуса отправки
        await db.submissions.update_one(
            {"_id": ObjectId(submission_id)},
            {
                "$set": {
                    "status": "approved",
                    "reviewed_at": datetime.now(UTC)
                }
            }
        )
        
        # Обновление очков пользователя
        await db.users.update_one(
            {"user_id": submission["user_id"]},
            {
                "$inc": {"points": 20},
                "$push": {"completed_challenges": submission["challenge_id"]}
            }
        )
        
        # Уведомление пользователя
        await bot.send_message(
            submission["user_id"],
            "✅ Твой челлендж одобрен! +20 очков"
        )
        
        # Автоматическая публикация в канал, если это фото или видео
        try:
            channel_id = os.getenv("CHANNEL_ID")
            if channel_id and submission.get("media"):
                media_type = submission.get("media_type", "")
                media_file_id = submission.get("media")
                caption = f"Челлендж от @{submission.get('username', 'user')}\n\n{submission.get('text', '')}"
                if "photo" in media_type:
                    await bot.send_photo(channel_id, photo=media_file_id, caption=caption)
                elif "video" in media_type:
                    await bot.send_video(channel_id, video=media_file_id, caption=caption)
                # Уведомление пользователю
                await bot.send_message(
                    submission["user_id"],
                    "🎉 Твоё фото/видео опубликовано в официальном канале Sparkaph! Поздравляем!"
                )
        except Exception as e:
            logger.error(f"Ошибка при публикации в канал: {e}")
        
        await callback.answer("Задание одобрено!")
    except Exception as e:
        logger.error(f"Ошибка при одобрении задания: {e}")
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_submission(callback: CallbackQuery, state: FSMContext):
    try:
        if callback.from_user.id != ADMIN_ID:
            return
        
        submission_id = callback.data.split("_")[1]
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        
        if not submission:
            await callback.answer("Задание не найдено.")
            return
        
        # Сохраняем submission_id и message_id для дальнейшего использования
        await save_temp_data(state, submission_id, callback.message.message_id)
        
        # Запрашиваем причину отказа
        await callback.message.reply("Укажите причину отказа:")
        await state.set_state(AdminStates.waiting_for_reject_reason)
        
        await callback.answer("Введите причину отказа")
    except Exception as e:
        logger.error(f"Ошибка при отклонении задания: {e}")
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик причины отказа
@dp.message(AdminStates.waiting_for_reject_reason)
async def process_reject_reason(message: Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Получаем сохраненные данные
        data = await state.get_data()
        submission_id = data.get("submission_id")
        message_id = data.get("message_id")
        
        if not submission_id:
            await message.answer("Ошибка: не найден ID задания.")
            await state.clear()
            return
        
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await message.answer("Задание не найдено в базе данных.")
            await state.clear()
            return
        
        reject_reason = message.text
        
        # Обновление статуса отправки
        await db.submissions.update_one(
            {"_id": ObjectId(submission_id)},
            {
                "$set": {
                    "status": "rejected",
                    "reviewed_at": datetime.now(UTC),
                    "reject_reason": reject_reason
                }
            }
        )
        
        # Уведомление пользователя
        await bot.send_message(
            submission["user_id"],
            f"❌ Твой челлендж отклонен.\nПричина: {reject_reason}\nПопробуй еще раз!"
        )
        
        # Обновление сообщения с заданием
        try:
            # Получаем исходное сообщение
            original_message = await bot.get_message(message.chat.id, message_id)
            
            if original_message.photo:
                await original_message.edit_caption(
                    caption=f"{original_message.caption}\n\n❌ Отклонено\nПричина: {reject_reason}",
                    reply_markup=None
                )
            elif original_message.video:
                await original_message.edit_caption(
                    caption=f"{original_message.caption}\n\n❌ Отклонено\nПричина: {reject_reason}",
                    reply_markup=None
                )
            elif original_message.document:
                await original_message.edit_caption(
                    caption=f"{original_message.caption}\n\n❌ Отклонено\nПричина: {reject_reason}",
                    reply_markup=None
                )
            else:
                await original_message.edit_text(
                    f"{original_message.text}\n\n❌ Отклонено\nПричина: {reject_reason}",
                    reply_markup=None
                )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение: {e}")
            await message.reply("Задание отклонено, но не удалось обновить оригинальное сообщение.")
        
        await message.reply("Задание отклонено, пользователь уведомлен.")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при обработке причины отказа: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик нажатия кнопки добавления челленджа
@dp.callback_query(lambda c: c.data == "add_challenge")
async def start_add_challenge(callback: CallbackQuery, state: FSMContext):
    try:
        if callback.from_user.id != ADMIN_ID:
            return
        
        await callback.message.answer("Введите текст нового челленджа:")
        await state.set_state(AdminStates.waiting_for_challenge_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при добавлении челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик получения текста челленджа
@dp.message(AdminStates.waiting_for_challenge_text)
async def process_challenge_text(message: Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        challenge_text = message.text
        if not challenge_text:
            await message.answer("Текст челленджа не может быть пустым. Пожалуйста, введите текст:")
            return
        
        # Сохраняем текст челленджа
        await state.update_data(challenge_text=challenge_text)
        
        # Запрашиваем описание челленджа
        await message.answer("Введите описание челленджа (или отправьте 'skip' для пропуска):")
        await state.set_state(AdminStates.waiting_for_challenge_description)
    except Exception as e:
        logger.error(f"Ошибка при обработке текста челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик получения описания челленджа
@dp.message(AdminStates.waiting_for_challenge_description)
async def process_challenge_description(message: Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        challenge_description = message.text
        
        # Если пользователь хочет пропустить описание
        if challenge_description.lower() == "skip":
            challenge_description = ""
        
        # Сохраняем описание челленджа
        await state.update_data(challenge_description=challenge_description)
        
        # Получаем список категорий для выбора
        categories = await db.categories.find().to_list(length=None)
        
        if not categories:
            await message.answer("Нет доступных категорий. Сначала создайте категорию.")
            await state.clear()
            return
        
        # Создаем клавиатуру с категориями
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
        
        for category in categories:
            keyboard.inline_keyboard.append([
                types.InlineKeyboardButton(
                    text=category["name"],
                    callback_data=f"select_category_{category['_id']}"
                )
            ])
        
        await message.answer("Выберите категорию для челленджа:", reply_markup=keyboard)
        await state.set_state(AdminStates.waiting_for_challenge_category)
    except Exception as e:
        logger.error(f"Ошибка при обработке описания челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик выбора категории для челленджа
@dp.callback_query(lambda c: c.data.startswith("select_category_"))
async def process_challenge_category(callback: CallbackQuery, state: FSMContext):
    try:
        if callback.from_user.id != ADMIN_ID:
            return
        
        # Получаем ID категории из callback_data
        category_id = callback.data.split("_")[2]
        
        # Сохраняем ID категории
        await state.update_data(category_id=ObjectId(category_id))
        
        # Запрашиваем максимальное количество участников
        await callback.message.edit_text("Введите максимальное количество участников для челленджа (по умолчанию 5):")
        await state.set_state(AdminStates.waiting_for_challenge_max_users)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при выборе категории челленджа: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик получения максимального количества участников
@dp.message(AdminStates.waiting_for_challenge_max_users)
async def process_challenge_max_users(message: Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Проверяем, что введено число
        max_users = 5  # По умолчанию
        
        try:
            if message.text:
                max_users = int(message.text)
                if max_users <= 0:
                    raise ValueError("Количество участников должно быть положительным")
        except ValueError:
            await message.answer("Пожалуйста, введите корректное число. Используем значение по умолчанию: 5")
        
        # Получаем сохраненные данные
        data = await state.get_data()
        
        # Создаем новый челлендж
        challenge = {
            "category_id": data["category_id"],
            "text": data["challenge_text"],
            "description": data.get("challenge_description", ""),
            "max_users": max_users,
            "taken_by": [],
            "status": "active",
            "created_at": datetime.now(UTC)
        }
        
        # Сохраняем челлендж в базе данных
        result = await db.challenges.insert_one(challenge)
        
        if result.inserted_id:
            # Получаем информацию о категории
            category = await db.categories.find_one({"_id": data["category_id"]})
            category_name = category["name"] if category else "Неизвестная категория"
            
            await message.answer(
                f"✅ Челлендж успешно добавлен!\n\n"
                f"Текст: {data['challenge_text']}\n"
                f"Категория: {category_name}\n"
                f"Макс. пользователей: {max_users}"
            )
        else:
            await message.answer("❌ Не удалось добавить челлендж. Пожалуйста, попробуйте позже.")
        
        # Очищаем состояние
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при добавлении челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик нажатия кнопки добавления категории
@dp.callback_query(lambda c: c.data == "add_category")
async def start_add_category(callback: CallbackQuery, state: FSMContext):
    try:
        if callback.from_user.id != ADMIN_ID:
            return
        
        await callback.message.answer("Введите название новой категории:")
        await state.set_state(AdminStates.waiting_for_category_name)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при добавлении категории: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик получения названия категории
@dp.message(AdminStates.waiting_for_category_name)
async def process_category_name(message: Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        category_name = message.text
        if not category_name:
            await message.answer("Название категории не может быть пустым. Пожалуйста, введите название:")
            return
        
        # Проверяем, существует ли уже категория с таким именем
        existing_category = await db.categories.find_one({"name": category_name})
        if existing_category:
            await message.answer(f"Категория с названием '{category_name}' уже существует. Пожалуйста, выберите другое название:")
            return
        
        # Сохраняем название категории
        await state.update_data(category_name=category_name)
        
        # Запрашиваем описание категории
        await message.answer("Введите описание категории:")
        await state.set_state(AdminStates.waiting_for_category_description)
    except Exception as e:
        logger.error(f"Ошибка при обработке названия категории: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик получения описания категории
@dp.message(AdminStates.waiting_for_category_description)
async def process_category_description(message: Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        category_description = message.text
        if not category_description:
            await message.answer("Описание категории не может быть пустым. Пожалуйста, введите описание:")
            return
        
        # Получаем сохраненные данные
        data = await state.get_data()
        
        # Создаем новую категорию
        category = {
            "name": data["category_name"],
            "description": category_description,
            "created_at": datetime.now(UTC)
        }
        
        # Сохраняем категорию в базе данных
        result = await db.categories.insert_one(category)
        
        if result.inserted_id:
            await message.answer(
                f"✅ Категория успешно добавлена!\n\n"
                f"Название: {data['category_name']}\n"
                f"Описание: {category_description}"
            )
        else:
            await message.answer("Не удалось сохранить категорию. Попробуйте еще раз.")
        
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при сохранении категории: {e}")
        await message.answer(f"Произошла ошибка: {e}")
        await state.clear()

# Управление инфлюенсерами
@dp.message_handler(commands=['manage_influencers'])
async def manage_influencers(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("Добавить инфлюенсера", callback_data="add_influencer"),
        types.InlineKeyboardButton("Удалить инфлюенсера", callback_data="remove_influencer"),
        types.InlineKeyboardButton("Список инфлюенсеров", callback_data="list_influencers"),
        types.InlineKeyboardButton("Статистика инфлюенсеров", callback_data="influencer_stats")
    )
    await message.answer("Управление инфлюенсерами:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "add_influencer")
async def add_influencer_start(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите ID пользователя, которого хотите сделать инфлюенсером:")
    await AdminStates.waiting_for_influencer_id.set()

@dp.message_handler(state=AdminStates.waiting_for_influencer_id)
async def add_influencer_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        # Проверяем существование пользователя
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            await message.answer("Пользователь не найден.")
            await state.finish()
            return
        
        # Показываем список категорий
        categories = await db.categories.find({"status": "active"}).to_list(length=None)
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for category in categories:
            keyboard.add(types.InlineKeyboardButton(
                category["name"],
                callback_data=f"select_category_{category['_id']}"
            ))
        
        await state.update_data(influencer_id=user_id)
        await message.answer("Выберите категорию для инфлюенсера:", reply_markup=keyboard)
        await AdminStates.waiting_for_influencer_category.set()
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID пользователя.")

@dp.callback_query_handler(lambda c: c.data.startswith("select_category_"), state=AdminStates.waiting_for_influencer_category)
async def add_influencer_category(callback_query: types.CallbackQuery, state: FSMContext):
    category_id = ObjectId(callback_query.data.split("_")[-1])
    data = await state.get_data()
    user_id = data["influencer_id"]
    
    # Добавляем инфлюенсера
    await db.influencers.insert_one({
        "user_id": user_id,
        "category_id": category_id,
        "created_at": datetime.utcnow(),
        "status": "active",
        "permissions": ["create_challenges", "edit_challenges", "view_stats"]
    })
    
    await callback_query.message.answer("Инфлюенсер успешно добавлен!")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "remove_influencer")
async def remove_influencer_start(callback_query: types.CallbackQuery):
    influencers = await db.influencers.find({"status": "active"}).to_list(length=None)
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for influencer in influencers:
        user = await db.users.find_one({"user_id": influencer["user_id"]})
        category = await db.categories.find_one({"_id": influencer["category_id"]})
        keyboard.add(types.InlineKeyboardButton(
            f"{user['username']} - {category['name']}",
            callback_data=f"remove_influencer_{influencer['user_id']}"
        ))
    
    await callback_query.message.answer("Выберите инфлюенсера для удаления:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("remove_influencer_"))
async def remove_influencer_confirm(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[-1])
    await db.influencers.update_one(
        {"user_id": user_id},
        {"$set": {"status": "inactive"}}
    )
    await callback_query.message.answer("Инфлюенсер успешно удален!")

@dp.callback_query_handler(lambda c: c.data == "list_influencers")
async def list_influencers(callback_query: types.CallbackQuery):
    influencers = await db.influencers.find({"status": "active"}).to_list(length=None)
    if not influencers:
        await callback_query.message.answer("Нет активных инфлюенсеров.")
        return
    
    text = "Список активных инфлюенсеров:\n\n"
    for influencer in influencers:
        user = await db.users.find_one({"user_id": influencer["user_id"]})
        category = await db.categories.find_one({"_id": influencer["category_id"]})
        text += f"@{user['username']} - {category['name']}\n"
    
    await callback_query.message.answer(text)

@dp.callback_query_handler(lambda c: c.data == "influencer_stats")
async def influencer_stats(callback_query: types.CallbackQuery):
    influencers = await db.influencers.find({"status": "active"}).to_list(length=None)
    if not influencers:
        await callback_query.message.answer("Нет активных инфлюенсеров.")
        return
    
    text = "Статистика инфлюенсеров:\n\n"
    for influencer in influencers:
        user = await db.users.find_one({"user_id": influencer["user_id"]})
        category = await db.categories.find_one({"_id": influencer["category_id"]})
        
        # Получаем статистику
        challenges_count = await db.challenges.count_documents({
            "created_by": influencer["user_id"]
        })
        active_challenges = await db.challenges.count_documents({
            "created_by": influencer["user_id"],
            "status": "active"
        })
        
        text += f"@{user['username']} - {category['name']}\n"
        text += f"Всего челленджей: {challenges_count}\n"
        text += f"Активных челленджей: {active_challenges}\n\n"
    
    await callback_query.message.answer(text)

# Массовое добавление челленджей
@dp.message_handler(commands=['bulk_add_challenges'])
async def bulk_add_challenges(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return
    
    await message.answer(
        "Отправьте файл с челленджами в формате CSV.\n"
        "Формат: category_name,text,description,max_users\n"
        "Пример: Фитнес,Пробежать 5км,Ежедневная пробежка,10"
    )
    await AdminStates.waiting_for_challenges_file.set()

@dp.message_handler(content_types=['document'], state=AdminStates.waiting_for_challenges_file)
async def process_challenges_file(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith('.csv'):
        await message.answer("Пожалуйста, отправьте файл в формате CSV.")
        return
    
    # Скачиваем файл
    file = await bot.get_file(message.document.file_id)
    file_path = file.file_path
    downloaded_file = await bot.download_file(file_path)
    
    # Читаем и обрабатываем файл
    success_count = 0
    error_count = 0
    
    for line in downloaded_file.read().decode().split('\n'):
        if not line.strip():
            continue
        
        try:
            category_name, text, description, max_users = line.strip().split(',')
            category = await db.categories.find_one({"name": category_name})
            
            if not category:
                error_count += 1
                continue
            
            await db.challenges.insert_one({
                "category_id": category["_id"],
                "text": text,
                "description": description,
                "max_users": int(max_users),
                "taken_by": [],
                "status": "active",
                "created_at": datetime.utcnow(),
                "created_by": message.from_user.id,
                "is_active": True
            })
            success_count += 1
        except Exception as e:
            error_count += 1
            continue
    
    await message.answer(
        f"Обработка файла завершена!\n"
        f"Успешно добавлено: {success_count}\n"
        f"Ошибок: {error_count}"
    )
    await state.finish()

# Добавляем команду для просмотра статистики системы
@dp.message(Command("system_stats"))
async def cmd_system_stats(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Получаем отчет о производительности
        report = await system_monitor.get_performance_report()
        
        if "error" in report:
            await message.answer(f"Ошибка получения статистики: {report['error']}")
            return
        
        # Формируем текст отчета
        text = (
            f"📊 **Статистика системы**\n\n"
            f"⏱ Период: {report['period']}\n\n"
            f"📈 **Средние значения:**\n"
            f"• CPU: {report['average']['cpu_percent']}%\n"
            f"• Память: {report['average']['memory_percent']}%\n"
            f"• Диск: {report['average']['disk_percent']}%\n\n"
            f"📉 **Пиковые значения:**\n"
            f"• CPU: {report['peak']['cpu_percent']}%\n"
            f"• Память: {report['peak']['memory_percent']}%\n"
            f"• Диск: {report['peak']['disk_percent']}%\n\n"
            f"⚠️ Количество алертов: {report['alerts_count']}"
        )
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики системы: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Добавляем команду для оптимизации базы данных
@dp.message(Command("optimize_db"))
async def cmd_optimize_db(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        await message.answer("🔄 Начинаю оптимизацию базы данных...")
        
        # Запускаем оптимизацию
        await system_monitor.optimize_database()
        
        await message.answer("✅ Оптимизация базы данных завершена!")
        
    except Exception as e:
        logger.error(f"Ошибка при оптимизации базы данных: {e}")
        await message.answer("Произошла ошибка при оптимизации. Пожалуйста, попробуйте позже.")

# Добавляем команду для просмотра статистики производительности
@dp.message(Command("performance"))
async def cmd_performance(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Получаем статистику производительности
        stats = performance_monitor.get_statistics()
        
        text = (
            f"⚡️ **Статистика производительности**\n\n"
            f"⏱ Аптайм: {stats['uptime']} секунд\n"
            f"📊 Количество запросов: {stats['requests_count']}\n"
            f"⏱ Среднее время ответа: {stats['average_response_time']} секунд\n"
            f"📈 Запросов в секунду: {stats['requests_per_second']}"
        )
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики производительности: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик команды /covers
@dp.message(Command("covers"))
async def cmd_covers(message: Message):
    """Показать меню управления обложками"""
    try:
        # Проверяем права администратора
        if str(message.from_user.id) != os.getenv("ADMIN_USER_ID"):
            await message.answer("У вас нет прав для использования этой команды.")
            return
        
        # Получаем последние 10 одобренных submissions с медиа
        submissions = await db.submissions.find({
            "status": "approved",
            "media_type": {"$in": ["photo", "video"]}
        }).sort("submitted_at", -1).limit(10).to_list(length=None)
        
        if not submissions:
            await message.answer("Нет доступных медиа для создания обложек.")
            return
        
        # Создаем клавиатуру с выбором медиа
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for submission in submissions:
            user = await db.users.find_one({"user_id": submission["user_id"]})
            username = user.get("username", "Unknown") if user else "Unknown"
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"📸 {username} - {submission['media_type']}",
                    callback_data=f"admin_cover_{submission['_id']}"
                )
            ])
        
        await message.answer(
            "🎨 Генератор обложек\n\n"
            "Выберите медиа для создания обложки:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка в команде covers: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора медиа для обложки
@dp.callback_query(lambda c: c.data.startswith("admin_cover_"))
async def handle_admin_cover_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора медиа для создания обложки"""
    try:
        submission_id = callback.data.split("_")[2]
        
        # Получаем информацию о submission
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await callback.answer("Медиа не найдено")
            return
        
        # Сохраняем ID submission в состоянии
        await state.update_data(selected_submission_id=submission_id)
        
        # Создаем клавиатуру с выбором формата
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="TikTok (9:16)", callback_data="admin_format_tiktok")],
                [InlineKeyboardButton(text="Instagram Stories (9:16)", callback_data="admin_format_insta_story")],
                [InlineKeyboardButton(text="Instagram Post (1:1)", callback_data="admin_format_insta_post")]
            ]
        )
        
        await callback.message.edit_text(
            "Выберите формат обложки:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при выборе медиа: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора формата обложки
@dp.callback_query(lambda c: c.data.startswith("admin_format_"))
async def handle_admin_format_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора формата обложки"""
    try:
        format_type = callback.data.split("_")[2]
        
        # Сохраняем формат в состоянии
        await state.update_data(selected_format=format_type)
        
        # Создаем клавиатуру с выбором стиля
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for style in cover_generator.get_available_styles():
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=style.capitalize(),
                    callback_data=f"admin_style_{style}"
                )
            ])
        
        await callback.message.edit_text(
            "Выберите стиль обложки:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при выборе формата: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора стиля обложки
@dp.callback_query(lambda c: c.data.startswith("admin_style_"))
async def handle_admin_style_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора стиля обложки"""
    try:
        style = callback.data.split("_")[2]
        
        # Получаем данные из состояния
        data = await state.get_data()
        submission_id = data.get("selected_submission_id")
        format_type = data.get("selected_format")
        
        if not submission_id or not format_type:
            await callback.message.edit_text("Ошибка: данные не найдены. Попробуйте снова.")
            return
        
        # Получаем информацию о submission
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await callback.message.edit_text("Медиа не найдено")
            return
        
        # Генерируем превью обложки
        preview = await cover_generator.generate_preview(
            submission=submission,
            format_type=format_type,
            style=style
        )
        
        if not preview:
            await callback.message.edit_text(
                "❌ Не удалось сгенерировать превью.\n"
                "Пожалуйста, попробуйте другой стиль или формат."
            )
            return
        
        # Отправляем превью
        await callback.message.answer_photo(
            photo=preview,
            caption="Превью обложки. Введите текст для обложки:"
        )
        
        # Сохраняем стиль в состоянии
        await state.update_data(selected_style=style)
        await state.set_state(AdminStates.waiting_for_cover_text)
        
    except Exception as e:
        logger.error(f"Ошибка при выборе стиля: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода текста для обложки
@dp.message(AdminStates.waiting_for_cover_text)
async def handle_cover_text(message: Message, state: FSMContext):
    """Обработчик ввода текста для обложки"""
    try:
        text = message.text
        
        # Получаем данные из состояния
        data = await state.get_data()
        submission_id = data.get("selected_submission_id")
        format_type = data.get("selected_format")
        style = data.get("selected_style")
        
        if not all([submission_id, format_type, style]):
            await message.answer("Ошибка: данные не найдены. Попробуйте снова.")
            await state.clear()
            return
        
        # Получаем информацию о submission
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            await message.answer("Медиа не найдено")
            await state.clear()
            return
        
        # Генерируем обложку
        cover = await cover_generator.generate_cover(
            submission=submission,
            format_type=format_type,
            style=style,
            text=text
        )
        
        if not cover:
            await message.answer(
                "❌ Не удалось сгенерировать обложку.\n"
                "Пожалуйста, попробуйте снова."
            )
            await state.clear()
            return
        
        # Отправляем обложку
        await message.answer_photo(
            photo=cover,
            caption=f"✅ Обложка готова!\n\n"
                   f"Формат: {format_type}\n"
                   f"Стиль: {style}\n"
                   f"Текст: {text}"
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при генерации обложки: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

# Основная функция
async def main():
    try:
        # Инициализируем MongoDB
        await init_mongodb()
        
        # Инициализируем мониторинг
        await init_monitoring(db)
        
        # Настраиваем параметры polling для избежания конфликтов
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Запускаем бота с настройками против конфликтов
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            polling_timeout=30,
            reset_webhook=True
        )
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

async def on_startup(dispatcher):
    """Действия при запуске бота"""
    try:
        # Сбрасываем все обновления, которые могли накопиться
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот успешно запущен")
    except Exception as e:
        logger.error(f"Ошибка при инициализации бота: {e}")

async def on_shutdown(dispatcher):
    """Действия при остановке бота"""
    try:
        # Закрываем соединение с MongoDB
        if not MOCK_DB and 'mongo_client' in globals():
            mongo_client.close()
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке бота: {e}")

# Команды для управления достижениями
@dp.message_handler(commands=['achievements'])
async def show_achievements_menu(message: types.Message):
    """Показать меню управления достижениями"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("➕ Создать достижение", callback_data="create_achievement"))
    keyboard.add(InlineKeyboardButton("📋 Список достижений", callback_data="list_achievements"))
    keyboard.add(InlineKeyboardButton("📊 Статистика", callback_data="achievement_stats"))
    keyboard.add(InlineKeyboardButton("⚙️ Настройки", callback_data="achievement_settings"))
    
    await message.answer(
        "🎯 Управление достижениями\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "create_achievement")
async def create_achievement_start(callback_query: types.CallbackQuery):
    """Начать создание достижения"""
    keyboard = InlineKeyboardMarkup()
    for achievement_type in AchievementType:
        keyboard.add(InlineKeyboardButton(
            achievement_type.value,
            callback_data=f"create_{achievement_type.value}"
        ))
    
    await callback_query.message.edit_text(
        "Выберите тип достижения:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith("create_"))
async def create_achievement_type(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка выбора типа достижения"""
    achievement_type = callback_query.data.replace("create_", "")
    await state.update_data(achievement_type=achievement_type)
    
    await AchievementStates.waiting_for_name.set()
    await callback_query.message.edit_text(
        "Введите название достижения:"
    )

@dp.message_handler(state=AchievementStates.waiting_for_name)
async def process_achievement_name(message: types.Message, state: FSMContext):
    """Обработка названия достижения"""
    await state.update_data(name=message.text)
    await AchievementStates.waiting_for_description.set()
    await message.answer("Введите описание достижения:")

@dp.message_handler(state=AchievementStates.waiting_for_description)
async def process_achievement_description(message: types.Message, state: FSMContext):
    """Обработка описания достижения"""
    await state.update_data(description=message.text)
    await AchievementStates.waiting_for_requirements.set()
    await message.answer("Введите требования для достижения (в формате JSON):")

@dp.message_handler(state=AchievementStates.waiting_for_requirements)
async def process_achievement_requirements(message: types.Message, state: FSMContext):
    """Обработка требований достижения"""
    try:
        requirements = eval(message.text)
        await state.update_data(requirements=requirements)
        
        data = await state.get_data()
        achievement_type = data.get("achievement_type")
        
        if achievement_type == AchievementType.SEASONAL.value:
            await AchievementStates.waiting_for_season.set()
            await message.answer("Введите сезон достижения:")
        elif achievement_type == AchievementType.COLLECTION.value:
            await AchievementStates.waiting_for_collection.set()
            await message.answer("Введите название коллекции:")
        elif achievement_type == AchievementType.EVENT.value:
            await AchievementStates.waiting_for_event.set()
            await message.answer("Введите название события:")
        elif achievement_type == AchievementType.SPECIAL.value:
            await AchievementStates.waiting_for_special.set()
            await message.answer("Введите специальные условия (в формате JSON):")
        else:
            await AchievementStates.waiting_for_rewards.set()
            await message.answer("Введите награды за достижение (в формате JSON):")
            
    except Exception as e:
        await message.answer(f"Ошибка в формате JSON: {e}\nПопробуйте еще раз:")

@dp.message_handler(state=AchievementStates.waiting_for_season)
async def process_achievement_season(message: types.Message, state: FSMContext):
    """Обработка сезона достижения"""
    await state.update_data(season=message.text)
    await AchievementStates.waiting_for_expires_at.set()
    await message.answer("Введите дату окончания сезона (в формате YYYY-MM-DD):")

@dp.message_handler(state=AchievementStates.waiting_for_collection)
async def process_achievement_collection(message: types.Message, state: FSMContext):
    """Обработка коллекции достижения"""
    await state.update_data(collection=message.text)
    await AchievementStates.waiting_for_rewards.set()
    await message.answer("Введите награды за достижение (в формате JSON):")

@dp.message_handler(state=AchievementStates.waiting_for_event)
async def process_achievement_event(message: types.Message, state: FSMContext):
    """Обработка события достижения"""
    await state.update_data(event=message.text)
    await AchievementStates.waiting_for_rewards.set()
    await message.answer("Введите награды за достижение (в формате JSON):")

@dp.message_handler(state=AchievementStates.waiting_for_special)
async def process_achievement_special(message: Message, state: FSMContext):
    """Обработка специальных условий достижения"""
    try:
        special = eval(message.text)
        await state.update_data(special=special)
        await AchievementStates.waiting_for_rewards.set()
        await message.answer("Введите награды за достижение (в формате JSON):")
    except Exception as e:
        await message.answer(f"Ошибка в формате JSON: {e}\nПопробуйте еще раз:")

@dp.message_handler(state=AchievementStates.waiting_for_rewards)
async def process_achievement_rewards(message: types.Message, state: FSMContext):
    """Обработка наград достижения"""
    try:
        rewards = eval(message.text)
        await state.update_data(rewards=rewards)
        
        data = await state.get_data()
        achievement_type = data.get("achievement_type")
        
        if achievement_type == AchievementType.SEASONAL.value:
            await AchievementStates.waiting_for_expires_at.set()
            await message.answer("Введите дату окончания сезона (в формате YYYY-MM-DD):")
        else:
            await AchievementStates.waiting_for_hidden.set()
            await message.answer("Скрытое достижение? (да/нет):")
            
    except Exception as e:
        await message.answer(f"Ошибка в формате JSON: {e}\nПопробуйте еще раз:")

@dp.message_handler(state=AchievementStates.waiting_for_expires_at)
async def process_achievement_expires_at(message: types.Message, state: FSMContext):
    """Обработка даты окончания достижения"""
    try:
        expires_at = datetime.strptime(message.text, "%Y-%m-%d")
        await state.update_data(expires_at=expires_at)
        await AchievementStates.waiting_for_hidden.set()
        await message.answer("Скрытое достижение? (да/нет):")
    except Exception as e:
        await message.answer(f"Ошибка в формате даты: {e}\nПопробуйте еще раз (YYYY-MM-DD):")

@dp.message_handler(state=AchievementStates.waiting_for_hidden)
async def process_achievement_hidden(message: types.Message, state: FSMContext):
    """Обработка скрытости достижения"""
    hidden = message.text.lower() == "да"
    await state.update_data(hidden=hidden)
    
    # Создаем достижение
    data = await state.get_data()
    achievement = Achievement(
        name=data["name"],
        description=data["description"],
        type=AchievementType(data["achievement_type"]),
        requirements=data["requirements"],
        rewards=data["rewards"],
        hidden=hidden,
        expires_at=data.get("expires_at"),
        season=data.get("season"),
        collection=data.get("collection"),
        event=data.get("event"),
        special=data.get("special")
    )
    
    # Сохраняем достижение
    success = await achievement_system.create_achievement(achievement)
    
    if success:
        await message.answer(
            f"✅ Достижение успешно создано!\n\n"
            f"🎯 {achievement.name}\n"
            f"📝 {achievement.description}\n"
            f"⭐️ {achievement.points} очков"
        )
    else:
        await message.answer("❌ Ошибка при создании достижения")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "list_achievements")
async def list_achievements(callback_query: types.CallbackQuery):
    """Показать список достижений"""
    achievements = await achievement_system.get_all_achievements()
    
    if not achievements:
        await callback_query.message.edit_text("Нет доступных достижений")
        return
    
    text = "📋 Список достижений:\n\n"
    for achievement in achievements:
        text += f"🎯 {achievement.name}\n"
        text += f"📝 {achievement.description}\n"
        text += f"⭐️ {achievement.points} очков\n"
        text += f"🔒 {'Скрытое' if achievement.hidden else 'Видимое'}\n"
        if achievement.expires_at:
            text += f"⏰ До: {achievement.expires_at.strftime('%Y-%m-%d')}\n"
        text += "\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="achievements"))
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "achievement_stats")
async def show_achievement_stats(callback_query: types.CallbackQuery):
    """Показать статистику достижений"""
    stats = await achievement_system.get_achievement_stats()
    
    text = "📊 Статистика достижений:\n\n"
    text += f"Всего достижений: {stats['total']}\n"
    text += f"Активных достижений: {stats['active']}\n"
    text += f"Скрытых достижений: {stats['hidden']}\n"
    text += f"Сезонных достижений: {stats['seasonal']}\n"
    text += f"Коллекций: {stats['collections']}\n"
    text += f"Событий: {stats['events']}\n"
    text += f"Специальных достижений: {stats['special']}\n\n"
    
    text += "По типам:\n"
    for type_name, count in stats["by_type"].items():
        text += f"{type_name}: {count}\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="achievements"))
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "achievement_settings")
async def show_achievement_settings(callback_query: types.CallbackQuery):
    """Показать настройки достижений"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📈 Настройки прогресса", callback_data="progress_settings"))
    keyboard.add(InlineKeyboardButton("🎁 Настройки наград", callback_data="reward_settings"))
    keyboard.add(InlineKeyboardButton("⚡️ Настройки бонусов", callback_data="bonus_settings"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="achievements"))
    
    await callback_query.message.edit_text(
        "⚙️ Настройки достижений\n\n"
        "Выберите категорию настроек:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "progress_settings")
async def show_progress_settings(callback_query: types.CallbackQuery):
    """Показать настройки прогресса"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📊 Настройки отображения", callback_data="progress_display"))
    keyboard.add(InlineKeyboardButton("⏰ Настройки времени", callback_data="progress_time"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="achievement_settings"))
    
    await callback_query.message.edit_text(
        "📈 Настройки прогресса\n\n"
        "Выберите настройку:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "reward_settings")
async def show_reward_settings(callback_query: types.CallbackQuery):
    """Показать настройки наград"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⭐️ Настройки очков", callback_data="points_settings"))
    keyboard.add(InlineKeyboardButton("🏅 Настройки бейджей", callback_data="badge_settings"))
    keyboard.add(InlineKeyboardButton("👑 Настройки титулов", callback_data="title_settings"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="achievement_settings"))
    
    await callback_query.message.edit_text(
        "🎁 Настройки наград\n\n"
        "Выберите настройку:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "bonus_settings")
async def show_bonus_settings(callback_query: types.CallbackQuery):
    """Показать настройки бонусов"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⏱ Настройки длительности", callback_data="bonus_duration"))
    keyboard.add(InlineKeyboardButton("📊 Настройки эффектов", callback_data="bonus_effects"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="achievement_settings"))
    
    await callback_query.message.edit_text(
        "⚡️ Настройки бонусов\n\n"
        "Выберите настройку:",
        reply_markup=keyboard
    )

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)