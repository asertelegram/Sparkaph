import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
from motor.motor_asyncio import AsyncIOMotorDatabase
from aiogram import Bot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentType(Enum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    STICKER = "sticker"
    ANIMATION = "animation"

class ModerationStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"

class ModerationAction(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    FLAG = "flag"
    DELETE = "delete"
    BAN = "ban"
    WARN = "warn"

@dataclass
class ModerationRule:
    content_type: ContentType
    pattern: str
    action: ModerationAction
    priority: int = 0
    description: str = ""

class ModerationSystem:
    def __init__(self, db: AsyncIOMotorDatabase, bot: Bot):
        self.db = db
        self.bot = bot
        self.rules = self._load_rules()
    
    def _load_rules(self) -> List[ModerationRule]:
        """Загрузка правил модерации"""
        return [
            # Правила для текста
            ModerationRule(
                content_type=ContentType.TEXT,
                pattern=r"(?i)(спам|реклама|купить|продать|заказать)",
                action=ModerationAction.REJECT,
                priority=1,
                description="Спам и реклама"
            ),
            ModerationRule(
                content_type=ContentType.TEXT,
                pattern=r"(?i)(оскорбление|ругательство|мат)",
                action=ModerationAction.REJECT,
                priority=2,
                description="Оскорбления"
            ),
            
            # Правила для фото
            ModerationRule(
                content_type=ContentType.PHOTO,
                pattern=r"nsfw|nude|porn",
                action=ModerationAction.REJECT,
                priority=3,
                description="NSFW контент"
            ),
            
            # Правила для видео
            ModerationRule(
                content_type=ContentType.VIDEO,
                pattern=r"nsfw|nude|porn",
                action=ModerationAction.REJECT,
                priority=3,
                description="NSFW контент"
            ),
            
            # Общие правила
            ModerationRule(
                content_type=ContentType.TEXT,
                pattern=r"(?i)(взлом|хак|взломать|хакать)",
                action=ModerationAction.FLAG,
                priority=2,
                description="Подозрительная активность"
            )
        ]
    
    async def moderate_content(
        self,
        content_type: ContentType,
        content: str,
        user_id: int,
        message_id: int,
        chat_id: int
    ) -> Dict[str, Any]:
        """Модерация контента"""
        try:
            # Проверяем правила
            for rule in self.rules:
                if rule.content_type == content_type:
                    if rule.pattern in content.lower():
                        # Применяем действие
                        if rule.action == ModerationAction.REJECT:
                            await self._reject_content(message_id, chat_id, rule.description)
                        elif rule.action == ModerationAction.FLAG:
                            await self._flag_content(message_id, chat_id, rule.description)
                        elif rule.action == ModerationAction.DELETE:
                            await self._delete_content(message_id, chat_id)
                        elif rule.action == ModerationAction.BAN:
                            await self._ban_user(user_id, chat_id, rule.description)
                        elif rule.action == ModerationAction.WARN:
                            await self._warn_user(user_id, chat_id, rule.description)
                        
                        # Сохраняем результат модерации
                        await self._save_moderation_result(
                            user_id=user_id,
                            content_type=content_type,
                            content=content,
                            action=rule.action,
                            reason=rule.description
                        )
                        
                        return {
                            "status": "moderated",
                            "action": rule.action.value,
                            "reason": rule.description
                        }
            
            # Если контент прошел проверку
            await self._save_moderation_result(
                user_id=user_id,
                content_type=content_type,
                content=content,
                action=ModerationAction.APPROVE,
                reason="Content passed moderation"
            )
            
            return {
                "status": "approved",
                "action": "approve",
                "reason": "Content passed moderation"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при модерации контента: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _reject_content(self, message_id: int, chat_id: int, reason: str):
        """Отклонение контента"""
        try:
            await self.bot.delete_message(chat_id, message_id)
            await self.bot.send_message(
                chat_id,
                f"❌ Сообщение удалено\nПричина: {reason}"
            )
        except Exception as e:
            logger.error(f"Ошибка при отклонении контента: {e}")
    
    async def _flag_content(self, message_id: int, chat_id: int, reason: str):
        """Пометка контента как подозрительного"""
        try:
            await self.bot.send_message(
                chat_id,
                f"⚠️ Внимание! Подозрительный контент\nПричина: {reason}"
            )
        except Exception as e:
            logger.error(f"Ошибка при пометке контента: {e}")
    
    async def _delete_content(self, message_id: int, chat_id: int):
        """Удаление контента"""
        try:
            await self.bot.delete_message(chat_id, message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении контента: {e}")
    
    async def _ban_user(self, user_id: int, chat_id: int, reason: str):
        """Бан пользователя"""
        try:
            await self.bot.ban_chat_member(chat_id, user_id)
            await self.bot.send_message(
                chat_id,
                f"🚫 Пользователь заблокирован\nПричина: {reason}"
            )
        except Exception as e:
            logger.error(f"Ошибка при бане пользователя: {e}")
    
    async def _warn_user(self, user_id: int, chat_id: int, reason: str):
        """Предупреждение пользователя"""
        try:
            await self.bot.send_message(
                chat_id,
                f"⚠️ Предупреждение пользователю\nПричина: {reason}"
            )
        except Exception as e:
            logger.error(f"Ошибка при предупреждении пользователя: {e}")
    
    async def _save_moderation_result(
        self,
        user_id: int,
        content_type: ContentType,
        content: str,
        action: ModerationAction,
        reason: str
    ):
        """Сохранение результата модерации"""
        try:
            await self.db.moderation_logs.insert_one({
                "user_id": user_id,
                "content_type": content_type.value,
                "content": content,
                "action": action.value,
                "reason": reason,
                "timestamp": datetime.now(UTC)
            })
        except Exception as e:
            logger.error(f"Ошибка при сохранении результата модерации: {e}")
    
    async def get_moderation_stats(self) -> Dict[str, Any]:
        """Получение статистики модерации"""
        try:
            total = await self.db.moderation_logs.count_documents({})
            approved = await self.db.moderation_logs.count_documents({"action": "approve"})
            rejected = await self.db.moderation_logs.count_documents({"action": "reject"})
            flagged = await self.db.moderation_logs.count_documents({"action": "flag"})
            deleted = await self.db.moderation_logs.count_documents({"action": "delete"})
            banned = await self.db.moderation_logs.count_documents({"action": "ban"})
            warned = await self.db.moderation_logs.count_documents({"action": "warn"})
            
            return {
                "total": total,
                "approved": approved,
                "rejected": rejected,
                "flagged": flagged,
                "deleted": deleted,
                "banned": banned,
                "warned": warned
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики модерации: {e}")
            return {
                "error": str(e)
            }
    
    async def add_moderation_rule(self, rule: ModerationRule) -> bool:
        """Добавление правила модерации"""
        try:
            self.rules.append(rule)
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении правила модерации: {e}")
            return False
    
    async def remove_moderation_rule(self, rule_index: int) -> bool:
        """Удаление правила модерации"""
        try:
            if 0 <= rule_index < len(self.rules):
                self.rules.pop(rule_index)
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при удалении правила модерации: {e}")
            return False
    
    async def get_moderation_rules(self) -> List[Dict[str, Any]]:
        """Получение списка правил модерации"""
        try:
            return [
                {
                    "content_type": rule.content_type.value,
                    "pattern": rule.pattern,
                    "action": rule.action.value,
                    "priority": rule.priority,
                    "description": rule.description
                }
                for rule in self.rules
            ]
        except Exception as e:
            logger.error(f"Ошибка при получении правил модерации: {e}")
            return []

    async def auto_moderate_user(self, user_id: int, complaints_limit: int = 3, warnings_limit: int = 2, ban_system=None, complaint_system=None, admin_id: int = 0):
        """Автоматическая модерация пользователя по количеству жалоб и предупреждений"""
        try:
            # Получаем количество жалоб
            complaints_count = 0
            if complaint_system:
                complaints = await complaint_system.get_user_complaints(user_id, limit=100)
                complaints_count = len([c for c in complaints if c.get('status') == 'pending'])
            # Получаем количество предупреждений
            warnings_count = 0
            if ban_system:
                warnings = await ban_system.get_user_warnings(user_id)
                warnings_count = len(warnings)
            # Если превышен лимит жалоб — бан
            if complaints_count >= complaints_limit and ban_system:
                await ban_system.ban_user(user_id, admin_id, reason=f"Автоматический бан: {complaints_count} жалоб", duration_hours=24)
                return {"action": "ban", "reason": f"{complaints_count} жалоб"}
            # Если превышен лимит предупреждений — бан
            if warnings_count >= warnings_limit and ban_system:
                await ban_system.ban_user(user_id, admin_id, reason=f"Автоматический бан: {warnings_count} предупреждений", duration_hours=24)
                return {"action": "ban", "reason": f"{warnings_count} предупреждений"}
            # Если есть жалобы — варн
            if complaints_count > 0 and ban_system:
                await ban_system.warn_user(user_id, admin_id, reason=f"Автоматическое предупреждение: {complaints_count} жалоб")
                return {"action": "warn", "reason": f"{complaints_count} жалоб"}
            return {"action": "none"}
        except Exception as e:
            logger.error(f"Ошибка авто-модерации: {e}")
            return {"action": "error", "error": str(e)} 