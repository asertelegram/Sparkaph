import os
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any, Union
import asyncio
import random
import base64
from bson import ObjectId
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

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

# Инициализация клиента MongoDB
try:
    MONGODB_URI = os.getenv("MONGODB_URI")
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI отсутствует в .env файле")
    
    mongo_client = AsyncIOMotorClient(MONGODB_URI)
    db = mongo_client.Sparkaph
    logger.info("Подключение к MongoDB установлено")
except Exception as e:
    logger.error(f"Ошибка подключения к MongoDB: {e}")
    raise

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

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "Unknown"
        
        # Проверка существования пользователя
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            # Создание нового пользователя
            new_user = {
                "user_id": user_id,
                "username": username,
                "points": 0,
                "current_challenge": None,
                "completed_challenges": [],
                "subscription": False,
                "joined_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "gender": None,
                "age": None,
                "location": None,
                "invited_by": None
            }
            
            await db.users.insert_one(new_user)
            
            # Запускаем процесс регистрации с запросом пола
            await message.answer(
                "👋 Добро пожаловать в Sparkaph!\n\n"
                "Для лучшего опыта, расскажите немного о себе.\n"
                "Ваш пол:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Мужской", callback_data="gender_male")],
                        [InlineKeyboardButton(text="Женский", callback_data="gender_female")],
                        [InlineKeyboardButton(text="Пропустить", callback_data="gender_skip")]
                    ]
                )
            )
            
            # Устанавливаем состояние ожидания ввода пола
            await state.set_state(UserStates.registering_gender)
            return
        
        # Обновление времени последней активности
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
        
        # Проверяем подписку пользователя
        is_subscribed = await check_subscription(user_id)
        
        if is_subscribed and not user.get("subscription"):
            # Автоматически обновляем статус подписки и начисляем очки
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"subscription": True}, "$inc": {"points": 10}}
            )
            await message.answer("Спасибо за подписку на наш канал! Тебе начислено 10 очков.")
        elif not is_subscribed and user.get("subscription"):
            # Если пользователь отписался от канала
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
                "Для продолжения использования бота, пожалуйста, подпишитесь на канал.",
                reply_markup=keyboard
            )
        
        welcome_text = f"Привет, {username}! Рад снова видеть тебя в Sparkaph!\n\n"
        
        if user.get("current_challenge"):
            # Если у пользователя есть активный челлендж, напоминаем о нем
            challenge = await db.challenges.find_one({"_id": user["current_challenge"]})
            if challenge:
                welcome_text += f"У тебя есть активный челлендж: {challenge['text']}\n\n"
        
        welcome_text += f"Твои очки: {user.get('points', 0)}\n"
        welcome_text += "Используй меню, чтобы получить новые челленджи или посмотреть статистику."
        
        await message.answer(welcome_text, reply_markup=get_main_menu())
        
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()

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
            [types.KeyboardButton(text="👥 Пригласить друга"), types.KeyboardButton(text="📞 Поддержка")]
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
            await message.answer("К сожалению, сейчас нет доступных челленджей ни в одной категории. Попробуй позже.")
        
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
            f"Выполнено челленджей: {total_completed}\n\n"
        )
        
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
        
        # Определяем достижения пользователя
        # Можно добавить логику для разных уровней и достижений
        level = 1
        if total_completed >= 5:
            level = 2
        if total_completed >= 15:
            level = 3
        if total_completed >= 30:
            level = 4
        if total_completed >= 50:
            level = 5
            
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
    invite_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user_id}"
    
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

# Основная функция
async def main():
    try:
        logger.info("Запуск пользовательского бота")
        # Запускаем фоновую задачу для напоминаний
        asyncio.create_task(reminder_scheduler())
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

# Функция для отправки напоминаний
async def send_challenge_reminder():
    try:
        # Находим пользователей с активными челленджами
        current_time = datetime.now(UTC)
        
        # Получаем всех пользователей с активными челленджами
        users = await db.users.find({"current_challenge": {"$ne": None}}).to_list(length=None)
        
        for user in users:
            # Находим челлендж пользователя
            challenge = await db.challenges.find_one({"_id": user["current_challenge"]})
            if not challenge:
                continue
                
            # Проверяем, когда был взят челлендж
            # Для этого добавим в будущем поле challenge_started_at в данные пользователя
            challenge_started_at = user.get("challenge_started_at")
            
            if not challenge_started_at:
                continue
                
            # Рассчитываем, сколько времени прошло с начала челленджа
            time_passed = (current_time - challenge_started_at).total_seconds() / 3600  # в часах
            
            # Если прошло около 6 часов (между 5.9 и 6.1)
            if 5.9 <= time_passed <= 6.1 and not user.get("first_reminder_sent"):
                await bot.send_message(
                    user["user_id"],
                    "🔔 Напоминание: Ты не забыл выполнить свой челлендж? У тебя осталось 6 часов!"
                )
                # Отмечаем, что первое напоминание отправлено
                await db.users.update_one(
                    {"user_id": user["user_id"]},
                    {"$set": {"first_reminder_sent": True}}
                )
                
            # Если прошло около 10 часов (между 9.9 и 10.1)
            elif 9.9 <= time_passed <= 10.1 and not user.get("second_reminder_sent"):
                await bot.send_message(
                    user["user_id"],
                    "⏰ Срочное напоминание: Осталось всего 2 часа на выполнение челленджа! Не упусти шанс!"
                )
                # Отмечаем, что второе напоминание отправлено
                await db.users.update_one(
                    {"user_id": user["user_id"]},
                    {"$set": {"second_reminder_sent": True}}
                )
                
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминаний: {e}")

# Планировщик напоминаний, запускается каждые 30 минут
async def reminder_scheduler():
    while True:
        try:
            await send_challenge_reminder()
        except Exception as e:
            logger.error(f"Ошибка в планировщике напоминаний: {e}")
        
        # Ждем 30 минут перед следующей проверкой
        await asyncio.sleep(30 * 60)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Не удалось запустить бота: {e}")
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}") 