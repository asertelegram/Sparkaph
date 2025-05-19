import os
import logging
from datetime import datetime, UTC, timedelta
from typing import Optional, List, Dict
from bson import ObjectId
import json
from pytz import UTC

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pymongo import MongoClient

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получение токена из переменных окружения
BOT_TOKEN = os.getenv("INFLUENCER_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("INFLUENCER_BOT_TOKEN отсутствует в .env файле")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключение к MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# Класс-заглушка для базы данных
class MockDatabase:
    def __init__(self):
        self.collections = {}
    
    def __getattr__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]

class MockCollection:
    async def find_one(self, *args, **kwargs):
        return None
    
    async def find(self, *args, **kwargs):
        return []
    
    async def count_documents(self, *args, **kwargs):
        return 0
    
    async def insert_one(self, *args, **kwargs):
        return None
    
    async def update_one(self, *args, **kwargs):
        return None
    
    async def delete_one(self, *args, **kwargs):
        return None
    
    async def create_index(self, *args, **kwargs):
        return None

# Инициализация MongoDB клиента
try:
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client["Sparkaph"]  # Используем единое название с большой буквы
    logger.info("MongoDB клиент инициализирован")
except Exception as e:
    logger.error(f"Ошибка при инициализации базы данных: {e}")
    # Создаем заглушку для базы данных
    db = MockDatabase()

# Состояния для FSM
class InfluencerStates(StatesGroup):
    waiting_for_challenge_text = State()
    waiting_for_challenge_type = State()
    waiting_for_challenge_description = State()
    waiting_for_edit_text = State()
    waiting_for_edit_description = State()
    waiting_for_challenge_id = State()
    waiting_for_schedule_date = State()
    waiting_for_schedule_time = State()
    waiting_for_archive_reason = State()
    waiting_for_template_name = State()
    waiting_for_template_text = State()
    waiting_for_template_type = State()
    waiting_for_template_description = State()

# Проверка является ли пользователь инфлюенсером
async def is_influencer(user_id: int) -> bool:
    """Check if user is an influencer"""
    influencer = await db.influencers.find_one({"user_id": user_id})
    return bool(influencer)

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "Unknown"
        
        # Проверяем, является ли пользователь инфлюенсером
        if not await is_influencer(user_id):
            await message.answer(
                "⚠️ У вас нет доступа к этому боту.\n"
                "Этот бот предназначен только для инфлюенсеров."
            )
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        category = await db.categories.find_one({"_id": influencer["category_id"]})
        
        # Получаем статистику
        challenges_count = await db.challenges.count_documents({"category_id": influencer["category_id"]})
        completed_count = await db.submissions.count_documents({
            "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
            "status": "approved"
        })
        
        # Получаем статистику за последние 7 дней
        week_ago = datetime.now(UTC) - timedelta(days=7)
        weekly_completed = await db.submissions.count_documents({
            "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
            "status": "approved",
            "submitted_at": {"$gte": week_ago}
        })
        
        # Получаем количество активных пользователей
        active_users = await db.users.count_documents({
            "last_activity": {"$gte": week_ago}
        })
        
        # Получаем среднее время выполнения
        submissions = await db.submissions.find({
            "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
            "status": "approved",
            "submitted_at": {"$gte": week_ago}
        }).to_list(length=None)
        
        avg_completion_time = 0
        if submissions:
            completion_times = []
            for submission in submissions:
                if submission.get("submitted_at") and submission.get("challenge_id"):
                    challenge = await db.challenges.find_one({"_id": submission["challenge_id"]})
                    if challenge and challenge.get("created_at"):
                        time_diff = (submission["submitted_at"] - challenge["created_at"]).total_seconds() / 3600
                        completion_times.append(time_diff)
            if completion_times:
                avg_completion_time = sum(completion_times) / len(completion_times)
        
        welcome_text = (
            f"👋 Привет, {username}!\n\n"
            f"Вы управляете категорией: {category['name']}\n\n"
            f"📊 Статистика вашей категории:\n"
            f"• Всего челленджей: {challenges_count}\n"
            f"• Выполнено: {completed_count}\n"
            f"• За последнюю неделю: {weekly_completed}\n"
            f"• Активных пользователей: {active_users}\n"
            f"• Среднее время выполнения: {avg_completion_time:.1f} часов\n\n"
            "Выберите действие в меню ниже:"
        )
        
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="➕ Добавить челлендж"), types.KeyboardButton(text="📋 Мои челленджи")],
                [types.KeyboardButton(text="📊 Статистика"), types.KeyboardButton(text="📅 Запланированные")],
                [types.KeyboardButton(text="📝 Шаблоны"), types.KeyboardButton(text="⚙️ Управление челленджами")],
                [types.KeyboardButton(text="🎯 Челлендж недели"), types.KeyboardButton(text="📱 Интеграции")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(welcome_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик добавления челленджа
@dp.message(lambda m: m.text == "➕ Добавить челлендж")
async def add_challenge(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        await message.answer(
            "Введите текст челленджа:\n"
            "Например: 'Сделай 50 отжиманий'"
        )
        await state.set_state(InfluencerStates.waiting_for_challenge_text)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода текста челленджа
@dp.message(InfluencerStates.waiting_for_challenge_text)
async def process_challenge_text(message: Message, state: FSMContext):
    try:
        await state.update_data(challenge_text=message.text)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📸 Фото", callback_data="type_photo"),
                    InlineKeyboardButton(text="🎥 Видео", callback_data="type_video")
                ],
                [InlineKeyboardButton(text="📝 Текст", callback_data="type_text")]
            ]
        )
        
        await message.answer(
            "Выберите тип ответа для челленджа:",
            reply_markup=keyboard
        )
        await state.set_state(InfluencerStates.waiting_for_challenge_type)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке текста челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора типа челленджа
@dp.message(InfluencerStates.waiting_for_challenge_type)
async def process_challenge_type(message: Message, state: FSMContext):
    try:
        challenge_type = message.text.split("_")[1]
        await state.update_data(challenge_type=challenge_type)
        
        await message.answer(
            "Введите описание челленджа:\n"
            "Например: 'Сделай фото или видео выполнения упражнения'"
        )
        await state.set_state(InfluencerStates.waiting_for_challenge_description)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке типа челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода описания челленджа
@dp.message(InfluencerStates.waiting_for_challenge_description)
async def process_challenge_description(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        data = await state.get_data()
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Создаем новый челлендж
        new_challenge = {
            "text": data["challenge_text"],
            "description": message.text,
            "type": data["challenge_type"],
            "category_id": influencer["category_id"],
            "created_by": user_id,
            "created_at": datetime.now(UTC),
            "is_active": True
        }
        
        result = await db.challenges.insert_one(new_challenge)
        
        await message.answer(
            "✅ Челлендж успешно добавлен!\n\n"
            f"Текст: {data['challenge_text']}\n"
            f"Тип: {data['challenge_type']}\n"
            f"Описание: {message.text}"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке описания челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик просмотра своих челленджей
@dp.message(lambda m: m.text == "📋 Мои челленджи")
async def show_my_challenges(message: Message):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем все челленджи инфлюенсера
        challenges = await db.challenges.find(
            {"category_id": influencer["category_id"]}
        ).sort("created_at", -1).to_list(length=None)
        
        if not challenges:
            await message.answer("У вас пока нет добавленных челленджей.")
            return
        
        text = "📋 Ваши челленджи:\n\n"
        
        for i, challenge in enumerate(challenges, 1):
            # Получаем статистику выполнения
            completed_count = await db.submissions.count_documents({
                "challenge_id": challenge["_id"],
                "status": "approved"
            })
            
            text += (
                f"{i}. {challenge['text']}\n"
                f"   Тип: {challenge['type']}\n"
                f"   Выполнено: {completed_count} раз\n"
                f"   Добавлен: {challenge['created_at'].strftime('%d.%m.%Y')}\n\n"
            )
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Ошибка при показе челленджей: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик управления челленджами
@dp.message(lambda m: m.text == "⚙️ Управление челленджами")
async def manage_challenges(message: Message):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем все челленджи инфлюенсера
        challenges = await db.challenges.find(
            {"category_id": influencer["category_id"]}
        ).sort("created_at", -1).to_list(length=None)
        
        if not challenges:
            await message.answer("У вас пока нет добавленных челленджей.")
            return
        
        text = "📋 Выберите челлендж для управления:\n\n"
        
        keyboard = []
        for challenge in challenges:
            completed_count = await db.submissions.count_documents({
                "challenge_id": challenge["_id"],
                "status": "approved"
            })
            
            status = "✅ Активен" if challenge.get("is_active", True) else "📦 В архиве"
            if challenge.get("scheduled_for"):
                status = f"📅 Запланирован на {challenge['scheduled_for'].strftime('%d.%m.%Y %H:%M')}"
            
            text += (
                f"• {challenge['text']}\n"
                f"  Выполнено: {completed_count} раз\n"
                f"  Статус: {status}\n\n"
            )
            
            keyboard.append([
                InlineKeyboardButton(
                    text=f"✏️ Изменить '{challenge['text'][:20]}...'",
                    callback_data=f"edit_{challenge['_id']}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ Удалить '{challenge['text'][:20]}...'",
                    callback_data=f"delete_{challenge['_id']}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    text=f"📦 Архивировать '{challenge['text'][:20]}...'",
                    callback_data=f"archive_{challenge['_id']}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    text=f"📅 Запланировать '{challenge['text'][:20]}...'",
                    callback_data=f"schedule_{challenge['_id']}"
                )
            ])
        
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        
    except Exception as e:
        logger.error(f"Ошибка при управлении челленджами: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик редактирования челленджа
@dp.callback_query(lambda c: c.data.startswith("edit_"))
async def edit_challenge(callback: CallbackQuery, state: FSMContext):
    try:
        challenge_id = callback.data.split("_")[1]
        challenge = await db.challenges.find_one({"_id": ObjectId(challenge_id)})
        
        if not challenge:
            await callback.answer("Челлендж не найден")
            return
        
        await state.update_data(editing_challenge_id=challenge_id)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text"),
                    InlineKeyboardButton(text="📝 Изменить описание", callback_data="edit_description")
                ],
                [InlineKeyboardButton(text="🔄 Изменить тип", callback_data="edit_type")]
            ]
        )
        
        await callback.message.edit_text(
            f"Выберите, что хотите изменить в челлендже:\n\n"
            f"Текущий текст: {challenge['text']}\n"
            f"Текущее описание: {challenge['description']}\n"
            f"Текущий тип: {challenge['type']}",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при редактировании челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик редактирования текста челленджа
@dp.callback_query(lambda c: c.data == "edit_text")
async def edit_challenge_text(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(InfluencerStates.waiting_for_edit_text)
        await callback.message.edit_text(
            "Введите новый текст челленджа:"
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании текста челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода нового текста челленджа
@dp.message(InfluencerStates.waiting_for_edit_text)
async def process_edit_text(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        challenge_id = data.get("editing_challenge_id")
        
        if not challenge_id:
            await message.answer("Ошибка: не найден ID челленджа")
            await state.clear()
            return
        
        # Обновляем текст челленджа
        await db.challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {"$set": {"text": message.text}}
        )
        
        await message.answer("✅ Текст челленджа успешно обновлен!")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке нового текста челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик редактирования описания челленджа
@dp.callback_query(lambda c: c.data == "edit_description")
async def edit_challenge_description(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(InfluencerStates.waiting_for_edit_description)
        await callback.message.edit_text(
            "Введите новое описание челленджа:"
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании описания челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода нового описания челленджа
@dp.message(InfluencerStates.waiting_for_edit_description)
async def process_edit_description(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        challenge_id = data.get("editing_challenge_id")
        
        if not challenge_id:
            await message.answer("Ошибка: не найден ID челленджа")
            await state.clear()
            return
        
        # Обновляем описание челленджа
        await db.challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {"$set": {"description": message.text}}
        )
        
        await message.answer("✅ Описание челленджа успешно обновлено!")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке нового описания челленджа: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик редактирования типа челленджа
@dp.callback_query(lambda c: c.data == "edit_type")
async def edit_challenge_type(callback: CallbackQuery, state: FSMContext):
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📸 Фото", callback_data="edit_type_photo"),
                    InlineKeyboardButton(text="🎥 Видео", callback_data="edit_type_video")
                ],
                [InlineKeyboardButton(text="📝 Текст", callback_data="edit_type_text")]
            ]
        )
        
        await callback.message.edit_text(
            "Выберите новый тип ответа для челленджа:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании типа челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора нового типа челленджа
@dp.callback_query(lambda c: c.data.startswith("edit_type_"))
async def process_edit_type(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        challenge_id = data.get("editing_challenge_id")
        
        if not challenge_id:
            await callback.answer("Ошибка: не найден ID челленджа")
            await state.clear()
            return
        
        new_type = callback.data.split("_")[2]
        
        # Обновляем тип челленджа
        await db.challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {"$set": {"type": new_type}}
        )
        
        await callback.message.edit_text("✅ Тип челленджа успешно обновлен!")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке нового типа челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик удаления челленджа
@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_challenge(callback: CallbackQuery):
    try:
        challenge_id = callback.data.split("_")[1]
        
        # Проверяем, есть ли активные выполнения
        active_submissions = await db.submissions.count_documents({
            "challenge_id": ObjectId(challenge_id),
            "status": "pending"
        })
        
        if active_submissions > 0:
            await callback.answer(
                "Нельзя удалить челлендж, пока есть ожидающие проверки выполнения",
                show_alert=True
            )
            return
        
        # Удаляем челлендж
        await db.challenges.delete_one({"_id": ObjectId(challenge_id)})
        
        await callback.message.edit_text("✅ Челлендж успешно удален!")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик архивирования челленджа
@dp.callback_query(lambda c: c.data.startswith("archive_"))
async def archive_challenge(callback: CallbackQuery, state: FSMContext):
    try:
        challenge_id = callback.data.split("_")[1]
        challenge = await db.challenges.find_one({"_id": ObjectId(challenge_id)})
        
        if not challenge:
            await callback.answer("Челлендж не найден")
            return
        
        await state.update_data(archiving_challenge_id=challenge_id)
        await state.set_state(InfluencerStates.waiting_for_archive_reason)
        
        await callback.message.edit_text(
            "Введите причину архивирования челленджа:"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при архивировании челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода причины архивирования
@dp.message(InfluencerStates.waiting_for_archive_reason)
async def process_archive_reason(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        challenge_id = data["archiving_challenge_id"]
        
        # Архивируем челлендж
        await db.challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {
                "$set": {
                    "is_active": False,
                    "archived_at": datetime.now(UTC),
                    "archive_reason": message.text
                }
            }
        )
        
        await message.answer("✅ Челлендж успешно архивирован!")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке причины архивирования: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик планирования челленджа
@dp.callback_query(lambda c: c.data.startswith("schedule_"))
async def schedule_challenge(callback: CallbackQuery, state: FSMContext):
    try:
        challenge_id = callback.data.split("_")[1]
        challenge = await db.challenges.find_one({"_id": ObjectId(challenge_id)})
        
        if not challenge:
            await callback.answer("Челлендж не найден")
            return
        
        await state.update_data(scheduling_challenge_id=challenge_id)
        await state.set_state(InfluencerStates.waiting_for_schedule_date)
        
        await callback.message.edit_text(
            "Введите дату публикации в формате ДД.ММ.ГГГГ:"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при планировании челленджа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода даты планирования
@dp.message(InfluencerStates.waiting_for_schedule_date)
async def process_schedule_date(message: Message, state: FSMContext):
    try:
        try:
            date = datetime.strptime(message.text, "%d.%m.%Y")
            if date < datetime.now():
                await message.answer("Дата должна быть в будущем. Попробуйте еще раз:")
                return
        except ValueError:
            await message.answer("Неверный формат даты. Используйте формат ДД.ММ.ГГГГ:")
            return
        
        await state.update_data(schedule_date=date)
        await state.set_state(InfluencerStates.waiting_for_schedule_time)
        
        await message.answer("Введите время публикации в формате ЧЧ:ММ:")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке даты планирования: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода времени планирования
@dp.message(InfluencerStates.waiting_for_schedule_time)
async def process_schedule_time(message: Message, state: FSMContext):
    try:
        try:
            time = datetime.strptime(message.text, "%H:%M").time()
        except ValueError:
            await message.answer("Неверный формат времени. Используйте формат ЧЧ:ММ:")
            return
        
        data = await state.get_data()
        date = data["schedule_date"]
        scheduled_datetime = datetime.combine(date.date(), time)
        
        if scheduled_datetime < datetime.now():
            await message.answer("Время должно быть в будущем. Попробуйте еще раз:")
            return
        
        # Обновляем челлендж
        await db.challenges.update_one(
            {"_id": ObjectId(data["scheduling_challenge_id"])},
            {
                "$set": {
                    "scheduled_for": scheduled_datetime,
                    "is_active": False
                }
            }
        )
        
        await message.answer(
            f"✅ Челлендж запланирован на {scheduled_datetime.strftime('%d.%m.%Y %H:%M')}!"
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке времени планирования: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик просмотра запланированных челленджей
@dp.message(lambda m: m.text == "📅 Запланированные")
async def show_scheduled_challenges(message: Message):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем запланированные челленджи
        challenges = await db.challenges.find({
            "category_id": influencer["category_id"],
            "scheduled_for": {"$exists": True, "$ne": None},
            "scheduled_for": {"$gt": datetime.now(UTC)}
        }).sort("scheduled_for", 1).to_list(length=None)
        
        if not challenges:
            await message.answer("У вас нет запланированных челленджей.")
            return
        
        text = "📅 Запланированные челленджи:\n\n"
        
        for i, challenge in enumerate(challenges, 1):
            text += (
                f"{i}. {challenge['text']}\n"
                f"   Запланирован на: {challenge['scheduled_for'].strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Ошибка при показе запланированных челленджей: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик просмотра статистики
@dp.message(lambda m: m.text == "📊 Статистика")
async def show_statistics(message: Message):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем статистику
        challenges_count = await db.challenges.count_documents({"category_id": influencer["category_id"]})
        completed_count = await db.submissions.count_documents({
            "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
            "status": "approved"
        })
        
        # Статистика за последние 7 дней
        week_ago = datetime.now(UTC) - timedelta(days=7)
        weekly_completed = await db.submissions.count_documents({
            "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
            "status": "approved",
            "submitted_at": {"$gte": week_ago}
        })
        
        # Статистика по типам ответов
        type_stats = {}
        challenges = await db.challenges.find({"category_id": influencer["category_id"]}).to_list(length=None)
        
        for challenge in challenges:
            submissions = await db.submissions.find({
                "challenge_id": challenge["_id"],
                "status": "approved"
            }).to_list(length=None)
            
            for submission in submissions:
                media_type = submission.get("media_type", "text")
                if media_type in type_stats:
                    type_stats[media_type] += 1
                else:
                    type_stats[media_type] = 1
        
        # Статистика по времени выполнения
        time_stats = {
            "morning": 0,  # 6-12
            "day": 0,      # 12-18
            "evening": 0,  # 18-24
            "night": 0     # 0-6
        }
        
        # Статистика по дням недели
        weekday_stats = {
            "monday": 0,
            "tuesday": 0,
            "wednesday": 0,
            "thursday": 0,
            "friday": 0,
            "saturday": 0,
            "sunday": 0
        }
        
        # Статистика по времени выполнения
        for challenge in challenges:
            submissions = await db.submissions.find({
                "challenge_id": challenge["_id"],
                "status": "approved"
            }).to_list(length=None)
            
            for submission in submissions:
                hour = submission["submitted_at"].hour
                weekday = submission["submitted_at"].strftime("%A").lower()
                
                if 6 <= hour < 12:
                    time_stats["morning"] += 1
                elif 12 <= hour < 18:
                    time_stats["day"] += 1
                elif 18 <= hour < 24:
                    time_stats["evening"] += 1
                else:
                    time_stats["night"] += 1
                
                weekday_stats[weekday] += 1
        
        # Получаем топ пользователей
        top_users = await db.submissions.aggregate([
            {
                "$match": {
                    "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
                    "status": "approved"
                }
            },
            {
                "$group": {
                    "_id": "$user_id",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$limit": 5
            }
        ]).to_list(length=None)
        
        # Получаем информацию о пользователях
        top_users_info = []
        for user in top_users:
            user_info = await db.users.find_one({"_id": user["_id"]})
            if user_info:
                top_users_info.append({
                    "username": user_info.get("username", "Unknown"),
                    "count": user["count"]
                })
        
        text = (
            f"📊 Статистика вашей категории:\n\n"
            f"Общая статистика:\n"
            f"• Всего челленджей: {challenges_count}\n"
            f"• Выполнено: {completed_count}\n"
            f"• За последнюю неделю: {weekly_completed}\n\n"
            f"По типам ответов:\n"
        )
        
        for media_type, count in type_stats.items():
            text += f"• {media_type}: {count}\n"
        
        text += "\nПо времени выполнения:\n"
        text += f"• Утро (6-12): {time_stats['morning']}\n"
        text += f"• День (12-18): {time_stats['day']}\n"
        text += f"• Вечер (18-24): {time_stats['evening']}\n"
        text += f"• Ночь (0-6): {time_stats['night']}\n"
        
        text += "\nПо дням недели:\n"
        weekday_names = {
            "monday": "Понедельник",
            "tuesday": "Вторник",
            "wednesday": "Среда",
            "thursday": "Четверг",
            "friday": "Пятница",
            "saturday": "Суббота",
            "sunday": "Воскресенье"
        }
        for weekday, count in weekday_stats.items():
            text += f"• {weekday_names[weekday]}: {count}\n"
        
        if top_users_info:
            text += "\nТоп пользователей:\n"
            for i, user in enumerate(top_users_info, 1):
                text += f"{i}. @{user['username']}: {user['count']} выполнено\n"
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик управления шаблонами
@dp.message(lambda m: m.text == "📝 Шаблоны")
async def manage_templates(message: Message):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем шаблоны инфлюенсера
        templates = await db.templates.find(
            {"created_by": user_id}
        ).sort("created_at", -1).to_list(length=None)
        
        if not templates:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать шаблон", callback_data="create_template")]
                ]
            )
            await message.answer(
                "У вас пока нет сохраненных шаблонов.\n"
                "Создайте шаблон для быстрого добавления похожих челленджей.",
                reply_markup=keyboard
            )
            return
        
        text = "📝 Ваши шаблоны:\n\n"
        
        keyboard = []
        for template in templates:
            text += (
                f"• {template['name']}\n"
                f"  Тип: {template['type']}\n"
                f"  Использовано: {template.get('usage_count', 0)} раз\n\n"
            )
            
            keyboard.append([
                InlineKeyboardButton(
                    text=f"📋 Использовать '{template['name']}'",
                    callback_data=f"use_template_{template['_id']}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ Удалить '{template['name']}'",
                    callback_data=f"delete_template_{template['_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton(text="➕ Создать шаблон", callback_data="create_template")])
        
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        
    except Exception as e:
        logger.error(f"Ошибка при управлении шаблонами: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик создания шаблона
@dp.callback_query(lambda c: c.data == "create_template")
async def create_template(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(InfluencerStates.waiting_for_template_name)
        await callback.message.edit_text(
            "Введите название шаблона:"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании шаблона: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода названия шаблона
@dp.message(InfluencerStates.waiting_for_template_name)
async def process_template_name(message: Message, state: FSMContext):
    try:
        await state.update_data(template_name=message.text)
        await state.set_state(InfluencerStates.waiting_for_template_text)
        
        await message.answer(
            "Введите текст челленджа для шаблона:\n"
            "Например: 'Сделай {количество} {упражнение}'"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке названия шаблона: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода текста шаблона
@dp.message(InfluencerStates.waiting_for_template_text)
async def process_template_text(message: Message, state: FSMContext):
    try:
        await state.update_data(template_text=message.text)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📸 Фото", callback_data="template_type_photo"),
                    InlineKeyboardButton(text="🎥 Видео", callback_data="template_type_video")
                ],
                [InlineKeyboardButton(text="📝 Текст", callback_data="template_type_text")]
            ]
        )
        
        await message.answer(
            "Выберите тип ответа для шаблона:",
            reply_markup=keyboard
        )
        await state.set_state(InfluencerStates.waiting_for_template_type)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке текста шаблона: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора типа шаблона
@dp.message(InfluencerStates.waiting_for_template_type)
@dp.callback_query(InfluencerStates.waiting_for_template_type)
async def process_template_type(callback: CallbackQuery, state: FSMContext):
    try:
        template_type = callback.data.split("_")[2]
        await state.update_data(template_type=template_type)
        await state.set_state(InfluencerStates.waiting_for_template_description)
        
        await callback.message.edit_text(
            "Введите описание шаблона:\n"
            "Например: 'Сделай фото или видео выполнения упражнения'"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке типа шаблона: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик ввода описания шаблона
@dp.message(InfluencerStates.waiting_for_template_description)
async def process_template_description(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        data = await state.get_data()
        
        # Создаем новый шаблон
        new_template = {
            "name": data["template_name"],
            "text": data["template_text"],
            "description": message.text,
            "type": data["template_type"],
            "created_by": user_id,
            "created_at": datetime.now(UTC),
            "usage_count": 0
        }
        
        result = await db.templates.insert_one(new_template)
        
        await message.answer(
            "✅ Шаблон успешно создан!\n\n"
            f"Название: {data['template_name']}\n"
            f"Текст: {data['template_text']}\n"
            f"Тип: {data['template_type']}\n"
            f"Описание: {message.text}"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке описания шаблона: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик использования шаблона
@dp.callback_query(lambda c: c.data.startswith("use_template_"))
async def use_template(callback: CallbackQuery, state: FSMContext):
    try:
        template_id = callback.data.split("_")[2]
        template = await db.templates.find_one({"_id": ObjectId(template_id)})
        
        if not template:
            await callback.answer("Шаблон не найден")
            return
        
        # Обновляем счетчик использования
        await db.templates.update_one(
            {"_id": ObjectId(template_id)},
            {"$inc": {"usage_count": 1}}
        )
        
        # Создаем новый челлендж из шаблона
        user_id = callback.from_user.id
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        new_challenge = {
            "text": template["text"],
            "description": template["description"],
            "type": template["type"],
            "category_id": influencer["category_id"],
            "created_by": user_id,
            "created_at": datetime.now(UTC),
            "is_active": True,
            "template_id": template["_id"]
        }
        
        result = await db.challenges.insert_one(new_challenge)
        
        await callback.message.edit_text(
            "✅ Челлендж успешно создан из шаблона!\n\n"
            f"Текст: {template['text']}\n"
            f"Тип: {template['type']}\n"
            f"Описание: {template['description']}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при использовании шаблона: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик удаления шаблона
@dp.callback_query(lambda c: c.data.startswith("delete_template_"))
async def delete_template(callback: CallbackQuery):
    try:
        template_id = callback.data.split("_")[2]
        
        # Проверяем, используется ли шаблон
        active_challenges = await db.challenges.count_documents({
            "template_id": ObjectId(template_id),
            "is_active": True
        })
        
        if active_challenges > 0:
            await callback.answer(
                "Нельзя удалить шаблон, пока есть активные челленджи, созданные из него",
                show_alert=True
            )
            return
        
        # Удаляем шаблон
        await db.templates.delete_one({"_id": ObjectId(template_id)})
        
        await callback.message.edit_text("✅ Шаблон успешно удален!")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении шаблона: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для челленджа недели
@dp.message(lambda m: m.text == "🎯 Челлендж недели")
async def manage_weekly_challenge(message: Message):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем текущий челлендж недели
        current_weekly = await get_weekly_challenge(influencer["category_id"])
        
        if current_weekly:
            # Получаем статистику выполнения
            completed_count = await db.submissions.count_documents({
                "challenge_id": current_weekly["challenge_id"],
                "status": "approved"
            })
            
            text = (
                "🎯 Текущий челлендж недели:\n\n"
                f"Текст: {current_weekly['text']}\n"
                f"Выполнено: {completed_count} раз\n"
                f"До конца: {current_weekly['end_date'].strftime('%d.%m.%Y')}\n\n"
                "Выберите действие:"
            )
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="weekly_stats")],
                    [InlineKeyboardButton(text="❌ Завершить досрочно", callback_data="end_weekly")]
                ]
            )
        else:
            text = (
                "🎯 Челлендж недели\n\n"
                "Сейчас нет активного челленджа недели.\n"
                "Выберите челлендж для назначения:"
            )
            
            # Получаем все активные челленджи инфлюенсера
            challenges = await db.challenges.find({
                "category_id": influencer["category_id"],
                "is_active": True
            }).sort("created_at", -1).to_list(length=None)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for challenge in challenges:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=challenge["text"],
                        callback_data=f"set_weekly_{challenge['_id']}"
                    )
                ])
        
        await message.answer(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при управлении челленджем недели: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для интеграций
@dp.message(lambda m: m.text == "📱 Интеграции")
async def manage_integrations(message: Message):
    try:
        user_id = message.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем настройки интеграций
        integrations = await db.integrations.find_one({"influencer_id": user_id})
        
        text = "📱 Интеграции с социальными сетями\n\n"
        
        if integrations:
            text += (
                f"TikTok: {'✅' if integrations.get('tiktok_enabled') else '❌'}\n"
                f"Instagram: {'✅' if integrations.get('instagram_enabled') else '❌'}\n\n"
                "Выберите действие:"
            )
        else:
            text += "Интеграции не настроены. Выберите платформу для подключения:"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="TikTok", callback_data="integrate_tiktok"),
                    InlineKeyboardButton(text="Instagram", callback_data="integrate_instagram")
                ],
                [InlineKeyboardButton(text="🎨 Генератор обложек", callback_data="cover_generator")]
            ]
        )
        
        await message.answer(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при управлении интеграциями: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для генератора обложек
@dp.callback_query(lambda c: c.data == "cover_generator")
async def cover_generator(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем последние выполненные челленджи
        submissions = await db.submissions.find({
            "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
            "status": "approved",
            "media_type": {"$in": ["photo", "video"]}
        }).sort("submitted_at", -1).limit(5).to_list(length=None)
        
        if not submissions:
            await callback.message.edit_text(
                "У вас пока нет выполненных челленджей с медиа для создания обложки."
            )
            return
        
        text = "🎨 Генератор обложек\n\n"
        text += "Выберите медиа для создания обложки:"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for submission in submissions:
            challenge = await db.challenges.find_one({"_id": submission["challenge_id"]})
            if challenge:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"📸 {challenge['text']}",
                        callback_data=f"generate_cover_{submission['_id']}"
                    )
                ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации обложки: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для создания обложки
@dp.callback_query(lambda c: c.data.startswith("generate_cover_"))
async def create_cover(callback: CallbackQuery):
    try:
        submission_id = callback.data.split("_")[2]
        submission = await db.submissions.find_one({"_id": ObjectId(submission_id)})
        
        if not submission:
            await callback.answer("Отправка не найдена")
            return
        
        # Здесь будет логика генерации обложки
        # Пока просто отправляем сообщение
        await callback.message.edit_text(
            "🎨 Генерация обложки...\n\n"
            "Функция находится в разработке. Скоро здесь появится возможность "
            "создавать красивые обложки для TikTok и Instagram!"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании обложки: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для установки челленджа недели
@dp.callback_query(lambda c: c.data.startswith("set_weekly_"))
async def set_weekly_challenge(callback: CallbackQuery):
    try:
        challenge_id = callback.data.split("_")[2]
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем информацию о челлендже
        challenge = await db.challenges.find_one({"_id": ObjectId(challenge_id)})
        if not challenge:
            await callback.answer("Челлендж не найден")
            return
        
        # Устанавливаем дату окончания (7 дней от текущей даты)
        end_date = datetime.now(UTC) + timedelta(days=7)
        
        # Создаем запись о челлендже недели
        weekly_challenge = {
            "challenge_id": challenge["_id"],
            "category_id": influencer["category_id"],
            "text": challenge["text"],
            "start_date": datetime.now(UTC),
            "end_date": end_date,
            "created_by": user_id
        }
        
        await db.weekly_challenges.insert_one(weekly_challenge)
        
        await callback.message.edit_text(
            "✅ Челлендж недели успешно установлен!\n\n"
            f"Текст: {challenge['text']}\n"
            f"Действует до: {end_date.strftime('%d.%m.%Y')}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при установке челленджа недели: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для статистики челленджа недели
@dp.callback_query(lambda c: c.data == "weekly_stats")
async def show_weekly_stats(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем текущий челлендж недели
        current_weekly = await get_weekly_challenge(influencer["category_id"])
        
        if not current_weekly:
            await callback.answer("Нет активного челленджа недели")
            return
        
        # Получаем статистику выполнения
        submissions = await db.submissions.find({
            "challenge_id": current_weekly["challenge_id"],
            "status": "approved"
        }).sort("submitted_at", -1).to_list(length=None)
        
        # Группируем по дням
        daily_stats = {}
        for submission in submissions:
            day = submission["submitted_at"].strftime("%d.%m.%Y")
            if day in daily_stats:
                daily_stats[day] += 1
            else:
                daily_stats[day] = 1
        
        # Формируем текст статистики
        text = "📊 Статистика челленджа недели:\n\n"
        text += f"Всего выполнено: {len(submissions)}\n\n"
        
        if daily_stats:
            text += "По дням:\n"
            for day, count in sorted(daily_stats.items()):
                text += f"• {day}: {count}\n"
        
        # Получаем топ пользователей
        top_users = await db.submissions.aggregate([
            {
                "$match": {
                    "challenge_id": current_weekly["challenge_id"],
                    "status": "approved"
                }
            },
            {
                "$group": {
                    "_id": "$user_id",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$limit": 5
            }
        ]).to_list(length=None)
        
        if top_users:
            text += "\nТоп пользователей:\n"
            for i, user in enumerate(top_users, 1):
                user_info = await db.users.find_one({"_id": user["_id"]})
                if user_info:
                    text += f"{i}. @{user_info.get('username', 'Unknown')} - {user['count']}\n"
        
        await callback.message.edit_text(text)
        
    except Exception as e:
        logger.error(f"Ошибка при показе статистики челленджа недели: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для завершения челленджа недели
@dp.callback_query(lambda c: c.data == "end_weekly")
async def end_weekly_challenge(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем текущий челлендж недели
        current_weekly = await get_weekly_challenge(influencer["category_id"])
        
        if not current_weekly:
            await callback.answer("Нет активного челленджа недели")
            return
        
        # Обновляем дату окончания
        await db.weekly_challenges.update_one(
            {"_id": current_weekly["_id"]},
            {"$set": {"end_date": datetime.now(UTC)}}
        )
        
        await callback.message.edit_text(
            "✅ Челлендж недели завершен!\n\n"
            "Вы можете установить новый челлендж недели."
        )
        
    except Exception as e:
        logger.error(f"Ошибка при завершении челленджа недели: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для интеграции с TikTok
@dp.callback_query(lambda c: c.data == "integrate_tiktok")
async def integrate_tiktok(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем текущие настройки интеграции
        integrations = await db.integrations.find_one({"influencer_id": user_id})
        
        if integrations and integrations.get("tiktok_enabled"):
            # Если интеграция уже включена, предлагаем отключить
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отключить TikTok", callback_data="disable_tiktok")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_integrations")]
                ]
            )
            
            await callback.message.edit_text(
                "TikTok уже подключен!\n\n"
                "Вы можете отключить интеграцию или вернуться назад.",
                reply_markup=keyboard
            )
        else:
            # Если интеграция не подключена, предлагаем подключить
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Подключить TikTok", url="https://tiktok.com/oauth/authorize")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_integrations")]
                ]
            )
            
            await callback.message.edit_text(
                "Для подключения TikTok:\n\n"
                "1. Нажмите кнопку 'Подключить TikTok'\n"
                "2. Авторизуйтесь в своем аккаунте\n"
                "3. Разрешите доступ к вашему аккаунту\n\n"
                "После этого вы сможете автоматически публиковать контент в TikTok.",
                reply_markup=keyboard
            )
        
    except Exception as e:
        logger.error(f"Ошибка при интеграции с TikTok: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для интеграции с Instagram
@dp.callback_query(lambda c: c.data == "integrate_instagram")
async def integrate_instagram(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем текущие настройки интеграции
        integrations = await db.integrations.find_one({"influencer_id": user_id})
        
        if integrations and integrations.get("instagram_enabled"):
            # Если интеграция уже включена, предлагаем отключить
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отключить Instagram", callback_data="disable_instagram")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_integrations")]
                ]
            )
            
            await callback.message.edit_text(
                "Instagram уже подключен!\n\n"
                "Вы можете отключить интеграцию или вернуться назад.",
                reply_markup=keyboard
            )
        else:
            # Если интеграция не подключена, предлагаем подключить
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Подключить Instagram", url="https://api.instagram.com/oauth/authorize")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_integrations")]
                ]
            )
            
            await callback.message.edit_text(
                "Для подключения Instagram:\n\n"
                "1. Нажмите кнопку 'Подключить Instagram'\n"
                "2. Авторизуйтесь в своем аккаунте\n"
                "3. Разрешите доступ к вашему аккаунту\n\n"
                "После этого вы сможете автоматически публиковать контент в Instagram.",
                reply_markup=keyboard
            )
        
    except Exception as e:
        logger.error(f"Ошибка при интеграции с Instagram: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для отключения TikTok
@dp.callback_query(lambda c: c.data == "disable_tiktok")
async def disable_tiktok(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Отключаем интеграцию
        await db.integrations.update_one(
            {"influencer_id": user_id},
            {"$set": {"tiktok_enabled": False, "tiktok_token": None}},
            upsert=True
        )
        
        await callback.message.edit_text(
            "✅ Интеграция с TikTok отключена!\n\n"
            "Вы можете подключить её снова в любое время."
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отключении TikTok: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для отключения Instagram
@dp.callback_query(lambda c: c.data == "disable_instagram")
async def disable_instagram(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Отключаем интеграцию
        await db.integrations.update_one(
            {"influencer_id": user_id},
            {"$set": {"instagram_enabled": False, "instagram_token": None}},
            upsert=True
        )
        
        await callback.message.edit_text(
            "✅ Интеграция с Instagram отключена!\n\n"
            "Вы можете подключить её снова в любое время."
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отключении Instagram: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик возврата к интеграциям
@dp.callback_query(lambda c: c.data == "back_to_integrations")
async def back_to_integrations(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        
        if not await is_influencer(user_id):
            return
        
        # Получаем информацию об инфлюенсере
        influencer = await db.influencers.find_one({"user_id": user_id})
        
        # Получаем настройки интеграций
        integrations = await db.integrations.find_one({"influencer_id": user_id})
        
        text = "📱 Интеграции с социальными сетями\n\n"
        
        if integrations:
            text += (
                f"TikTok: {'✅' if integrations.get('tiktok_enabled') else '❌'}\n"
                f"Instagram: {'✅' if integrations.get('instagram_enabled') else '❌'}\n\n"
                "Выберите действие:"
            )
        else:
            text += "Интеграции не настроены. Выберите платформу для подключения:"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="TikTok", callback_data="integrate_tiktok"),
                    InlineKeyboardButton(text="Instagram", callback_data="integrate_instagram")
                ],
                [InlineKeyboardButton(text="🎨 Генератор обложек", callback_data="cover_generator")]
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при возврате к интеграциям: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Функция для получения текущего челленджа недели
async def get_weekly_challenge(category_id: str) -> Optional[Dict]:
    try:
        current_time = datetime.now(UTC)
        weekly_challenge = await db.weekly_challenges.find_one({
            "category_id": category_id,
            "end_date": {"$gt": current_time}
        })
        return weekly_challenge
    except Exception as e:
        logger.error(f"Ошибка при получении челленджа недели: {e}")
        return None

# Инициализация базы данных
async def init_db():
    try:
        # Создаем индексы для коллекций
        await db.weekly_challenges.create_index([
            ("category_id", 1),
            ("end_date", 1)
        ])
        
        await db.integrations.create_index([
            ("influencer_id", 1)
        ])
        
        await db.submissions.create_index([
            ("challenge_id", 1),
            ("status", 1),
            ("submitted_at", -1)
        ])
        
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")

# Основная функция
async def main():
    try:
        logger.info("Запуск бота для инфлюенсеров")
        # Инициализируем базу данных
        await init_db()
        # Запускаем бота
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

def register_handlers(dispatcher):
    # Основные команды
    dispatcher.message.register(cmd_start, Command("start"))
    
    # Обработчики кнопок меню
    dispatcher.message.register(add_challenge, lambda m: m.text == "➕ Добавить челлендж")
    dispatcher.message.register(show_my_challenges, lambda m: m.text == "📋 Мои челленджи")
    dispatcher.message.register(manage_challenges, lambda m: m.text == "⚙️ Управление челленджами")
    dispatcher.message.register(show_scheduled_challenges, lambda m: m.text == "📅 Запланированные")
    dispatcher.message.register(show_statistics, lambda m: m.text == "📊 Статистика")
    dispatcher.message.register(manage_templates, lambda m: m.text == "📝 Шаблоны")
    dispatcher.message.register(manage_weekly_challenge, lambda m: m.text == "🎯 Челлендж недели")
    dispatcher.message.register(manage_integrations, lambda m: m.text == "📱 Интеграции")
    
    # Обработчики состояний FSM
    dispatcher.message.register(process_challenge_text, InfluencerStates.waiting_for_challenge_text)
    dispatcher.message.register(process_challenge_type, InfluencerStates.waiting_for_challenge_type)
    dispatcher.message.register(process_challenge_description, InfluencerStates.waiting_for_challenge_description)
    dispatcher.message.register(process_edit_text, InfluencerStates.waiting_for_edit_text)
    dispatcher.message.register(process_edit_description, InfluencerStates.waiting_for_edit_description)
    dispatcher.message.register(process_archive_reason, InfluencerStates.waiting_for_archive_reason)
    dispatcher.message.register(process_schedule_date, InfluencerStates.waiting_for_schedule_date)
    dispatcher.message.register(process_schedule_time, InfluencerStates.waiting_for_schedule_time)
    dispatcher.message.register(process_template_name, InfluencerStates.waiting_for_template_name)
    dispatcher.message.register(process_template_text, InfluencerStates.waiting_for_template_text)
    dispatcher.message.register(process_template_type, InfluencerStates.waiting_for_template_type)
    dispatcher.message.register(process_template_description, InfluencerStates.waiting_for_template_description)
    
    # Обработчики callback-запросов
    dispatcher.callback_query.register(edit_challenge, lambda c: c.data.startswith("edit_"))
    dispatcher.callback_query.register(delete_challenge, lambda c: c.data.startswith("delete_"))
    dispatcher.callback_query.register(archive_challenge, lambda c: c.data.startswith("archive_"))
    dispatcher.callback_query.register(schedule_challenge, lambda c: c.data.startswith("schedule_"))
    dispatcher.callback_query.register(edit_challenge_text, lambda c: c.data == "edit_text")
    dispatcher.callback_query.register(edit_challenge_description, lambda c: c.data == "edit_description")
    dispatcher.callback_query.register(edit_challenge_type, lambda c: c.data == "edit_type")
    dispatcher.callback_query.register(process_edit_type, lambda c: c.data.startswith("edit_type_"))
    dispatcher.callback_query.register(create_template, lambda c: c.data == "create_template")
    dispatcher.callback_query.register(use_template, lambda c: c.data.startswith("use_template_"))
    dispatcher.callback_query.register(delete_template, lambda c: c.data.startswith("delete_template_"))
    dispatcher.callback_query.register(set_weekly_challenge, lambda c: c.data.startswith("set_weekly_"))
    dispatcher.callback_query.register(show_weekly_stats, lambda c: c.data == "weekly_stats")
    dispatcher.callback_query.register(end_weekly_challenge, lambda c: c.data == "end_weekly")
    dispatcher.callback_query.register(integrate_tiktok, lambda c: c.data == "integrate_tiktok")
    dispatcher.callback_query.register(integrate_instagram, lambda c: c.data == "integrate_instagram")
    dispatcher.callback_query.register(disable_tiktok, lambda c: c.data == "disable_tiktok")
    dispatcher.callback_query.register(disable_instagram, lambda c: c.data == "disable_instagram")
    dispatcher.callback_query.register(back_to_integrations, lambda c: c.data == "back_to_integrations")
    dispatcher.callback_query.register(cover_generator, lambda c: c.data == "cover_generator")
    dispatcher.callback_query.register(create_cover, lambda c: c.data.startswith("generate_cover_"))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 