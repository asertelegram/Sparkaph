import logging
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from aiogram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BanStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

class BanSystem:
    def __init__(self, db: AsyncIOMotorDatabase, bot: Bot):
        self.db = db
        self.bot = bot

    async def ban_user(self, user_id: int, admin_id: int, reason: str, duration_hours: Optional[int] = None) -> bool:
        """Забанить пользователя (срок в часах, если None — навсегда)"""
        try:
            expires_at = None
            if duration_hours:
                expires_at = datetime.now(UTC) + timedelta(hours=duration_hours)
            await self.db.bans.insert_one({
                "user_id": user_id,
                "admin_id": admin_id,
                "reason": reason,
                "status": BanStatus.ACTIVE,
                "created_at": datetime.now(UTC),
                "expires_at": expires_at
            })
            await self.db.users.update_one({"user_id": user_id}, {"$set": {"banned": True}})
            return True
        except Exception as e:
            logger.error(f"Ошибка при бане пользователя: {e}")
            return False

    async def unban_user(self, user_id: int, admin_id: int, reason: str) -> bool:
        """Разбанить пользователя"""
        try:
            await self.db.bans.update_many(
                {"user_id": user_id, "status": BanStatus.ACTIVE},
                {"$set": {"status": BanStatus.REVOKED, "revoked_at": datetime.now(UTC), "revoke_reason": reason, "revoked_by": admin_id}}
            )
            await self.db.users.update_one({"user_id": user_id}, {"$set": {"banned": False}})
            return True
        except Exception as e:
            logger.error(f"Ошибка при разбане пользователя: {e}")
            return False

    async def warn_user(self, user_id: int, admin_id: int, reason: str) -> bool:
        """Вынести предупреждение пользователю"""
        try:
            await self.db.warnings.insert_one({
                "user_id": user_id,
                "admin_id": admin_id,
                "reason": reason,
                "created_at": datetime.now(UTC)
            })
            return True
        except Exception as e:
            logger.error(f"Ошибка при предупреждении пользователя: {e}")
            return False

    async def get_user_bans(self, user_id: int) -> List[Dict[str, Any]]:
        """История банов пользователя"""
        return await self.db.bans.find({"user_id": user_id}).sort("created_at", -1).to_list(length=None)

    async def get_user_warnings(self, user_id: int) -> List[Dict[str, Any]]:
        """История предупреждений пользователя"""
        return await self.db.warnings.find({"user_id": user_id}).sort("created_at", -1).to_list(length=None)

    async def get_ban_stats(self) -> Dict[str, int]:
        """Статистика по банам"""
        try:
            total = await self.db.bans.count_documents({})
            active = await self.db.bans.count_documents({"status": BanStatus.ACTIVE})
            expired = await self.db.bans.count_documents({"status": BanStatus.EXPIRED})
            revoked = await self.db.bans.count_documents({"status": BanStatus.REVOKED})
            warnings = await self.db.warnings.count_documents({})
            return {
                "total": total,
                "active": active,
                "expired": expired,
                "revoked": revoked,
                "warnings": warnings
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики банов: {e}")
            return {}

    async def check_expired_bans(self):
        """Проверить и снять истекшие баны"""
        now = datetime.now(UTC)
        expired = await self.db.bans.find({"status": BanStatus.ACTIVE, "expires_at": {"$lte": now}}).to_list(length=None)
        for ban in expired:
            await self.db.bans.update_one({"_id": ban["_id"]}, {"$set": {"status": BanStatus.EXPIRED, "expired_at": now}})
            await self.db.users.update_one({"user_id": ban["user_id"]}, {"$set": {"banned": False}}) 