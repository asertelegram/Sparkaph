import os
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, Union
from bson import ObjectId
import base64
import tempfile

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
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
    dp = Dispatcher()
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    raise

# Инициализация клиента MongoDB
try:
    mongo_client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = mongo_client.Sparkaph
except Exception as e:
    logger.error(f"Ошибка подключения к MongoDB: {e}")
    raise

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

# Вспомогательная функция для сохранения ID сообщения и submission_id
async def save_temp_data(state: FSMContext, submission_id: str, message_id: int):
    await state.update_data(submission_id=submission_id, message_id=message_id)

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
            [types.KeyboardButton(text="👥 Управление пользователями")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик проверки заданий
@dp.message(F.text == "📝 Проверить задания")
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

# Обработчик статистики
@dp.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        # Текущее время
        now = datetime.now(UTC)
        
        # Статистика за разные периоды
        stats = {}
        
        # Получение всех пользователей
        total_users = await db.users.count_documents({})
        stats["total_users"] = total_users
        
        # Получение активных пользователей (DAU - daily active users)
        active_users_24h = await db.users.count_documents({
            "last_activity": {"$gte": now - timedelta(days=1)}
        })
        stats["active_users_24h"] = active_users_24h
        
        # Активные пользователи за неделю (WAU - weekly active users)
        active_users_7d = await db.users.count_documents({
            "last_activity": {"$gte": now - timedelta(days=7)}
        })
        stats["active_users_7d"] = active_users_7d
        
        # Активные пользователи за 3 недели
        active_users_21d = await db.users.count_documents({
            "last_activity": {"$gte": now - timedelta(days=21)}
        })
        stats["active_users_21d"] = active_users_21d
        
        # Новые пользователи за последние 24 часа
        new_users_24h = await db.users.count_documents({
            "joined_at": {"$gte": now - timedelta(days=1)}
        })
        stats["new_users_24h"] = new_users_24h
        
        # Новые пользователи за последнюю неделю
        new_users_7d = await db.users.count_documents({
            "joined_at": {"$gte": now - timedelta(days=7)}
        })
        stats["new_users_7d"] = new_users_7d
        
        # Получение выполненных челленджей за разные периоды
        completed_challenges_total = await db.submissions.count_documents({
            "status": "approved"
        })
        stats["completed_challenges_total"] = completed_challenges_total
        
        completed_challenges_24h = await db.submissions.count_documents({
            "status": "approved",
            "reviewed_at": {"$gte": now - timedelta(days=1)}
        })
        stats["completed_challenges_24h"] = completed_challenges_24h
        
        completed_challenges_7d = await db.submissions.count_documents({
            "status": "approved",
            "reviewed_at": {"$gte": now - timedelta(days=7)}
        })
        stats["completed_challenges_7d"] = completed_challenges_7d
        
        # Статистика по категориям
        categories = await db.categories.find().to_list(length=None)
        category_stats = {}
        
        for category in categories:
            category_id = category["_id"]
            category_name = category["name"]
            
            # Количество челленджей в категории
            challenges_count = await db.challenges.count_documents({
                "category_id": category_id
            })
            
            # Количество выполненных челленджей в категории
            completed_in_category = 0
            challenges = await db.challenges.find({"category_id": category_id}).to_list(length=None)
            
            for challenge in challenges:
                # Проверяем выполненные пользователями
                submissions_count = await db.submissions.count_documents({
                    "challenge_id": challenge["_id"],
                    "status": "approved"
                })
                
                completed_in_category += submissions_count
            
            category_stats[category_name] = {
                "challenges_count": challenges_count,
                "completed_count": completed_in_category
            }
        
        # Получение среднего времени ответа за последнюю неделю
        submissions = await db.submissions.find({
            "status": {"$in": ["approved", "rejected"]},
            "submitted_at": {"$gte": now - timedelta(days=7)}
        }).to_list(length=None)
        
        avg_response_time = 0
        if submissions:
            response_times = []
            for submission in submissions:
                if submission.get("reviewed_at"):
                    response_time = submission["reviewed_at"] - submission["submitted_at"]
                    response_times.append(response_time.total_seconds() / 3600)
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        stats["avg_response_time_hours"] = avg_response_time
        
        # Расчет метрик удержания
        retention_1d = (active_users_24h / total_users * 100) if total_users > 0 else 0
        retention_7d = (active_users_7d / total_users * 100) if total_users > 0 else 0
        retention_21d = (active_users_21d / total_users * 100) if total_users > 0 else 0
        
        # Статистика по пользователям с подпиской на канал
        subscribed_users = await db.users.count_documents({"subscription": True})
        subscription_rate = (subscribed_users / total_users * 100) if total_users > 0 else 0
        
        # Получение демографических данных
        gender_stats = {
            "male": await db.users.count_documents({"gender": "male"}),
            "female": await db.users.count_documents({"gender": "female"}),
            "unknown": await db.users.count_documents({"gender": None})
        }
        
        age_stats = {
            "under18": await db.users.count_documents({"age": "under18"}),
            "18-24": await db.users.count_documents({"age": "18-24"}),
            "25-34": await db.users.count_documents({"age": "25-34"}),
            "35-44": await db.users.count_documents({"age": "35-44"}),
            "45plus": await db.users.count_documents({"age": "45plus"}),
            "unknown": await db.users.count_documents({"age": None})
        }
        
        # Формирование текста статистики (основные метрики)
        text = (
            f"📊 Основные метрики Sparkaph:\n\n"
            f"👥 Пользователи:\n"
            f"• Всего: {stats['total_users']}\n"
            f"• Активных за 24ч (DAU): {stats['active_users_24h']}\n"
            f"• Активных за неделю (WAU): {stats['active_users_7d']}\n"
            f"• Активных за 3 недели: {stats['active_users_21d']}\n"
            f"• Новых за 24ч: {stats['new_users_24h']}\n\n"
            
            f"🎯 Челленджи:\n"
            f"• Всего выполнено: {stats['completed_challenges_total']}\n"
            f"• Выполнено за 24ч: {stats['completed_challenges_24h']}\n"
            f"• Выполнено за неделю: {stats['completed_challenges_7d']}\n\n"
            
            f"⏱ Метрики времени:\n"
            f"• Среднее время проверки: {avg_response_time:.1f} ч\n\n"
            
            f"📈 Удержание:\n"
            f"• 1 день: {retention_1d:.1f}%\n"
            f"• 7 дней: {retention_7d:.1f}%\n"
            f"• 21 день: {retention_21d:.1f}%\n\n"
            
            f"📢 Подписка на канал: {subscription_rate:.1f}%\n\n"
        )
        
        # Отправляем основную статистику
        await message.answer(text)
        
        # Формируем статистику по категориям
        category_text = "📋 Статистика по категориям:\n\n"
        for name, data in category_stats.items():
            category_text += f"• {name}: {data['completed_count']} выполнено из {data['challenges_count']} челленджей\n"
        
        await message.answer(category_text)
        
        # Формируем демографическую статистику
        demo_text = (
            f"👤 Демографические данные:\n\n"
            f"Пол:\n"
            f"• Мужской: {gender_stats['male']} ({gender_stats['male']/total_users*100:.1f}%)\n"
            f"• Женский: {gender_stats['female']} ({gender_stats['female']/total_users*100:.1f}%)\n"
            f"• Не указан: {gender_stats['unknown']} ({gender_stats['unknown']/total_users*100:.1f}%)\n\n"
            
            f"Возраст:\n"
            f"• до 18: {age_stats['under18']} ({age_stats['under18']/total_users*100:.1f}%)\n"
            f"• 18-24: {age_stats['18-24']} ({age_stats['18-24']/total_users*100:.1f}%)\n"
            f"• 25-34: {age_stats['25-34']} ({age_stats['25-34']/total_users*100:.1f}%)\n"
            f"• 35-44: {age_stats['35-44']} ({age_stats['35-44']/total_users*100:.1f}%)\n"
            f"• 45+: {age_stats['45plus']} ({age_stats['45plus']/total_users*100:.1f}%)\n"
            f"• Не указан: {age_stats['unknown']} ({age_stats['unknown']/total_users*100:.1f}%)\n"
        )
        
        await message.answer(demo_text)
        
    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await message.answer(f"Произошла ошибка при сборе статистики: {e}")
        await message.answer("Попробуйте позже или обратитесь к разработчику.")

# Обработчики управления категориями
@dp.message(F.text == "📋 Управление категориями")
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
@dp.message(F.text == "🎯 Управление челленджами")
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
@dp.message(F.text == "👥 Управление пользователями")
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
@dp.callback_query(F.data.startswith("approve_"))
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
        
        # Обновление сообщения с заданием - обрабатываем разные типы сообщений
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=f"{callback.message.caption}\n\n✅ Одобрено",
                    reply_markup=None
                )
            elif callback.message.video:
                await callback.message.edit_caption(
                    caption=f"{callback.message.caption}\n\n✅ Одобрено",
                    reply_markup=None
                )
            elif callback.message.document:
                await callback.message.edit_caption(
                    caption=f"{callback.message.caption}\n\n✅ Одобрено",
                    reply_markup=None
                )
            else:
                await callback.message.edit_text(
                    f"{callback.message.text}\n\n✅ Одобрено",
                    reply_markup=None
                )
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения: {e}")
            # В случае ошибки отправляем новое сообщение
            await callback.message.answer("✅ Задание одобрено!")
        
        await callback.answer("Задание одобрено!")
    except Exception as e:
        logger.error(f"Ошибка при одобрении задания: {e}")
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(F.data.startswith("reject_"))
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
@dp.callback_query(F.data == "add_challenge")
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
@dp.callback_query(AdminStates.waiting_for_challenge_category, F.data.startswith("select_category_"))
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
            await message.answer("Не удалось сохранить челлендж. Попробуйте еще раз.")
        
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при сохранении челленджа: {e}")
        await message.answer(f"Произошла ошибка: {e}")
        await state.clear()

# Обработчик нажатия кнопки добавления категории
@dp.callback_query(F.data == "add_category")
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

# Основная функция
async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 