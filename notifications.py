import logging
from datetime import datetime, UTC
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from motor.motor_asyncio import AsyncIOMotorDatabase
from aiogram import Bot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationType(Enum):
    # Системные уведомления
    SYSTEM = "system"
    WELCOME = "welcome"
    ERROR = "error"
    
    # Уведомления о челленджах
    CHALLENGE_NEW = "challenge_new"
    CHALLENGE_REMINDER = "challenge_reminder"
    CHALLENGE_COMPLETED = "challenge_completed"
    CHALLENGE_APPROVED = "challenge_approved"
    CHALLENGE_REJECTED = "challenge_rejected"
    
    # Уведомления о достижениях
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    ACHIEVEMENT_PROGRESS = "achievement_progress"
    ACHIEVEMENT_SEASONAL = "achievement_seasonal"
    
    # Уведомления о прогрессе
    LEVEL_UP = "level_up"
    POINTS_EARNED = "points_earned"
    STREAK_UPDATED = "streak_updated"
    RANK_CHANGED = "rank_changed"
    
    # Социальные уведомления
    REFERRAL_JOINED = "referral_joined"
    SOCIAL_SHARE = "social_share"
    SOCIAL_LIKE = "social_like"
    SOCIAL_COMMENT = "social_comment"
    
    # Бонусные уведомления
    DAILY_BONUS = "daily_bonus"
    WEEKLY_BONUS = "weekly_bonus"
    SPECIAL_BONUS = "special_bonus"
    
    # События
    EVENT_STARTED = "event_started"
    EVENT_ENDING = "event_ending"
    EVENT_COMPLETED = "event_completed"
    
    # Напоминания
    REMINDER_DAILY = "reminder_daily"
    REMINDER_WEEKLY = "reminder_weekly"
    REMINDER_MONTHLY = "reminder_monthly"

@dataclass
class NotificationTemplate:
    type: NotificationType
    title: str
    message: str
    icon: str
    priority: int = 0
    requires_action: bool = False
    action_text: Optional[str] = None
    action_data: Optional[str] = None

class NotificationSystem:
    def __init__(self, db: AsyncIOMotorDatabase, bot: Bot):
        self.db = db
        self.bot = bot
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[NotificationType, NotificationTemplate]:
        """Загрузка шаблонов уведомлений"""
        return {
            # Системные уведомления
            NotificationType.SYSTEM: NotificationTemplate(
                type=NotificationType.SYSTEM,
                title="Системное уведомление",
                message="{message}",
                icon="🔔",
                priority=0
            ),
            NotificationType.WELCOME: NotificationTemplate(
                type=NotificationType.WELCOME,
                title="Добро пожаловать!",
                message="Добро пожаловать в Sparkaph! Начните свой путь к личностному росту прямо сейчас.",
                icon="👋",
                priority=1
            ),
            NotificationType.ERROR: NotificationTemplate(
                type=NotificationType.ERROR,
                title="Ошибка",
                message="Произошла ошибка: {error}",
                icon="❌",
                priority=2
            ),
            
            # Уведомления о челленджах
            NotificationType.CHALLENGE_NEW: NotificationTemplate(
                type=NotificationType.CHALLENGE_NEW,
                title="Новый челлендж",
                message="У вас новый челлендж: {challenge_name}\n\n{challenge_description}",
                icon="🎯",
                priority=1,
                requires_action=True,
                action_text="Начать челлендж",
                action_data="start_challenge_{challenge_id}"
            ),
            NotificationType.CHALLENGE_REMINDER: NotificationTemplate(
                type=NotificationType.CHALLENGE_REMINDER,
                title="Напоминание о челлендже",
                message="Не забудьте выполнить челлендж: {challenge_name}\nОсталось времени: {time_left}",
                icon="⏰",
                priority=1,
                requires_action=True,
                action_text="Выполнить челлендж",
                action_data="complete_challenge_{challenge_id}"
            ),
            NotificationType.CHALLENGE_COMPLETED: NotificationTemplate(
                type=NotificationType.CHALLENGE_COMPLETED,
                title="Челлендж выполнен",
                message="Поздравляем! Вы выполнили челлендж: {challenge_name}\nПолучено очков: {points}",
                icon="✅",
                priority=1
            ),
            NotificationType.CHALLENGE_APPROVED: NotificationTemplate(
                type=NotificationType.CHALLENGE_APPROVED,
                title="Челлендж одобрен",
                message="Ваш челлендж '{challenge_name}' был одобрен!\nПолучено очков: {points}",
                icon="🎉",
                priority=1
            ),
            NotificationType.CHALLENGE_REJECTED: NotificationTemplate(
                type=NotificationType.CHALLENGE_REJECTED,
                title="Челлендж отклонен",
                message="Ваш челлендж '{challenge_name}' был отклонен.\nПричина: {reason}",
                icon="❌",
                priority=1
            ),
            
            # Уведомления о достижениях
            NotificationType.ACHIEVEMENT_UNLOCKED: NotificationTemplate(
                type=NotificationType.ACHIEVEMENT_UNLOCKED,
                title="Новое достижение!",
                message="Поздравляем! Вы получили достижение:\n{achievement_name}\n{achievement_description}\nПолучено очков: {points}",
                icon="🏆",
                priority=2
            ),
            NotificationType.ACHIEVEMENT_PROGRESS: NotificationTemplate(
                type=NotificationType.ACHIEVEMENT_PROGRESS,
                title="Прогресс достижения",
                message="Прогресс достижения '{achievement_name}':\n{progress}% ({current}/{required})",
                icon="📊",
                priority=0
            ),
            NotificationType.ACHIEVEMENT_SEASONAL: NotificationTemplate(
                type=NotificationType.ACHIEVEMENT_SEASONAL,
                title="Сезонное достижение",
                message="Доступно новое сезонное достижение:\n{achievement_name}\n{achievement_description}\nДоступно до: {expires_at}",
                icon="🎄",
                priority=1,
                requires_action=True,
                action_text="Подробнее",
                action_data="view_seasonal_{achievement_id}"
            ),
            
            # Уведомления о прогрессе
            NotificationType.LEVEL_UP: NotificationTemplate(
                type=NotificationType.LEVEL_UP,
                title="Новый уровень!",
                message="Поздравляем! Вы достигли {level} уровня!\nПолучено бонусов: {bonus}",
                icon="⭐️",
                priority=2
            ),
            NotificationType.POINTS_EARNED: NotificationTemplate(
                type=NotificationType.POINTS_EARNED,
                title="Получены очки",
                message="Вы получили {points} очков!\nПричина: {reason}",
                icon="💎",
                priority=0
            ),
            NotificationType.STREAK_UPDATED: NotificationTemplate(
                type=NotificationType.STREAK_UPDATED,
                title="Обновление серии",
                message="Ваша серия: {streak} дней\nПолучено бонусов: {bonus}",
                icon="🔥",
                priority=1
            ),
            NotificationType.RANK_CHANGED: NotificationTemplate(
                type=NotificationType.RANK_CHANGED,
                title="Изменение ранга",
                message="Ваш новый ранг: {rank}\nПоздравляем!",
                icon="👑",
                priority=1
            ),
            
            # Социальные уведомления
            NotificationType.REFERRAL_JOINED: NotificationTemplate(
                type=NotificationType.REFERRAL_JOINED,
                title="Новый реферал",
                message="К вам присоединился новый реферал: {username}\nПолучено бонусов: {bonus}",
                icon="👥",
                priority=1
            ),
            NotificationType.SOCIAL_SHARE: NotificationTemplate(
                type=NotificationType.SOCIAL_SHARE,
                title="Поделились вашим контентом",
                message="Пользователь {username} поделился вашим контентом!\nПолучено очков: {points}",
                icon="📱",
                priority=0
            ),
            NotificationType.SOCIAL_LIKE: NotificationTemplate(
                type=NotificationType.SOCIAL_LIKE,
                title="Новый лайк",
                message="Пользователь {username} оценил ваш контент!",
                icon="❤️",
                priority=0
            ),
            NotificationType.SOCIAL_COMMENT: NotificationTemplate(
                type=NotificationType.SOCIAL_COMMENT,
                title="Новый комментарий",
                message="Пользователь {username} прокомментировал ваш контент:\n{comment}",
                icon="💬",
                priority=0
            ),
            
            # Бонусные уведомления
            NotificationType.DAILY_BONUS: NotificationTemplate(
                type=NotificationType.DAILY_BONUS,
                title="Ежедневный бонус",
                message="Ваш ежедневный бонус: {bonus}\nЗаходите каждый день!",
                icon="🎁",
                priority=1,
                requires_action=True,
                action_text="Получить бонус",
                action_data="claim_daily_bonus"
            ),
            NotificationType.WEEKLY_BONUS: NotificationTemplate(
                type=NotificationType.WEEKLY_BONUS,
                title="Еженедельный бонус",
                message="Ваш еженедельный бонус: {bonus}\nСпасибо за активность!",
                icon="🎁",
                priority=1,
                requires_action=True,
                action_text="Получить бонус",
                action_data="claim_weekly_bonus"
            ),
            NotificationType.SPECIAL_BONUS: NotificationTemplate(
                type=NotificationType.SPECIAL_BONUS,
                title="Специальный бонус",
                message="Специальный бонус: {bonus}\n{description}",
                icon="🎁",
                priority=2,
                requires_action=True,
                action_text="Получить бонус",
                action_data="claim_special_bonus_{bonus_id}"
            ),
            
            # Уведомления о событиях
            NotificationType.EVENT_STARTED: NotificationTemplate(
                type=NotificationType.EVENT_STARTED,
                title="Начало события",
                message="Началось новое событие: {event_name}\n{event_description}\nДоступно до: {ends_at}",
                icon="🎉",
                priority=2,
                requires_action=True,
                action_text="Участвовать",
                action_data="join_event_{event_id}"
            ),
            NotificationType.EVENT_ENDING: NotificationTemplate(
                type=NotificationType.EVENT_ENDING,
                title="Событие заканчивается",
                message="Событие '{event_name}' заканчивается через {time_left}!\nУспейте принять участие!",
                icon="⏰",
                priority=1,
                requires_action=True,
                action_text="Участвовать",
                action_data="join_event_{event_id}"
            ),
            NotificationType.EVENT_COMPLETED: NotificationTemplate(
                type=NotificationType.EVENT_COMPLETED,
                title="Событие завершено",
                message="Событие '{event_name}' завершено!\nВаш результат: {result}\nПолучено наград: {rewards}",
                icon="🎉",
                priority=1
            ),
            
            # Напоминания
            NotificationType.REMINDER_DAILY: NotificationTemplate(
                type=NotificationType.REMINDER_DAILY,
                title="Ежедневное напоминание",
                message="Не забудьте выполнить ежедневные задания!\nДоступно бонусов: {bonus}",
                icon="📅",
                priority=0,
                requires_action=True,
                action_text="Выполнить задания",
                action_data="show_daily_tasks"
            ),
            NotificationType.REMINDER_WEEKLY: NotificationTemplate(
                type=NotificationType.REMINDER_WEEKLY,
                title="Еженедельное напоминание",
                message="Не забудьте выполнить еженедельные задания!\nДоступно бонусов: {bonus}",
                icon="📅",
                priority=0,
                requires_action=True,
                action_text="Выполнить задания",
                action_data="show_weekly_tasks"
            ),
            NotificationType.REMINDER_MONTHLY: NotificationTemplate(
                type=NotificationType.REMINDER_MONTHLY,
                title="Ежемесячное напоминание",
                message="Не забудьте выполнить ежемесячные задания!\nДоступно бонусов: {bonus}",
                icon="📅",
                priority=0,
                requires_action=True,
                action_text="Выполнить задания",
                action_data="show_monthly_tasks"
            )
        }
    
    async def send_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        data: Dict[str, Any] = None,
        priority: Optional[int] = None
    ) -> bool:
        """Отправка уведомления пользователю"""
        try:
            # Проверяем настройки уведомлений пользователя
            user = await self.db.users.find_one({"user_id": user_id})
            if not user:
                return False
            
            # Если пользователь отключил уведомления, не отправляем
            if user.get("notifications_disabled", False):
                return False
            
            # Получаем шаблон уведомления
            template = self.templates.get(notification_type)
            if not template:
                logger.error(f"Шаблон уведомления не найден: {notification_type}")
                return False
            
            # Форматируем сообщение
            message = template.message.format(**(data or {}))
            
            # Создаем клавиатуру, если требуется действие
            keyboard = None
            if template.requires_action and template.action_text and template.action_data:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                action_data = template.action_data.format(**(data or {}))
                keyboard = InlineKeyboardMarkup().add(
                    InlineKeyboardButton(text=template.action_text, callback_data=action_data)
                )
            
            # Отправляем уведомление
            await self.bot.send_message(
                user_id,
                f"{template.icon} {template.title}\n\n{message}",
                reply_markup=keyboard
            )
            
            # Сохраняем уведомление в базу
            await self.db.notifications.insert_one({
                "user_id": user_id,
                "type": notification_type.value,
                "title": template.title,
                "message": message,
                "data": data,
                "priority": priority or template.priority,
                "sent_at": datetime.now(UTC)
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
            return False
    
    async def send_bulk_notification(
        self,
        user_ids: List[int],
        notification_type: NotificationType,
        data: Dict[str, Any] = None,
        priority: Optional[int] = None
    ) -> Dict[int, bool]:
        """Отправка уведомления нескольким пользователям"""
        results = {}
        for user_id in user_ids:
            results[user_id] = await self.send_notification(user_id, notification_type, data, priority)
        return results
    
    async def get_user_notifications(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
        notification_type: Optional[NotificationType] = None
    ) -> List[Dict[str, Any]]:
        """Получение уведомлений пользователя"""
        query = {"user_id": user_id}
        if notification_type:
            query["type"] = notification_type.value
        
        return await self.db.notifications.find(query).sort("sent_at", -1).skip(offset).limit(limit).to_list(length=None)
    
    async def mark_notification_as_read(self, notification_id: str) -> bool:
        """Отметить уведомление как прочитанное"""
        try:
            await self.db.notifications.update_one(
                {"_id": notification_id},
                {"$set": {"read": True, "read_at": datetime.now(UTC)}}
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отметке уведомления как прочитанного: {e}")
            return False
    
    async def delete_notification(self, notification_id: str) -> bool:
        """Удалить уведомление"""
        try:
            await self.db.notifications.delete_one({"_id": notification_id})
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении уведомления: {e}")
            return False
    
    async def clear_user_notifications(self, user_id: int) -> bool:
        """Очистить все уведомления пользователя"""
        try:
            await self.db.notifications.delete_many({"user_id": user_id})
            return True
        except Exception as e:
            logger.error(f"Ошибка при очистке уведомлений пользователя: {e}")
            return False
    
    async def get_unread_count(self, user_id: int) -> int:
        """Получить количество непрочитанных уведомлений"""
        return await self.db.notifications.count_documents({
            "user_id": user_id,
            "read": {"$ne": True}
        })
    
    async def get_notification_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику уведомлений пользователя"""
        total = await self.db.notifications.count_documents({"user_id": user_id})
        unread = await self.db.notifications.count_documents({
            "user_id": user_id,
            "read": {"$ne": True}
        })
        
        # Получаем количество уведомлений по типам
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}}
        ]
        type_stats = await self.db.notifications.aggregate(pipeline).to_list(length=None)
        
        return {
            "total": total,
            "unread": unread,
            "read": total - unread,
            "by_type": {stat["_id"]: stat["count"] for stat in type_stats}
        } 