import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from aiogram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComplaintStatus:
    PENDING = "pending"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    RESOLVED = "resolved"

class ComplaintSystem:
    def __init__(self, db: AsyncIOMotorDatabase, bot: Bot):
        self.db = db
        self.bot = bot

    async def submit_complaint(self, user_id: int, target_id: int, reason: str, content: Optional[str] = None) -> bool:
        """Подача жалобы на пользователя или контент"""
        try:
            await self.db.complaints.insert_one({
                "user_id": user_id,
                "target_id": target_id,
                "reason": reason,
                "content": content,
                "status": ComplaintStatus.PENDING,
                "created_at": datetime.now(UTC)
            })
            return True
        except Exception as e:
            logger.error(f"Ошибка при подаче жалобы: {e}")
            return False

    async def get_pending_complaints(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить список необработанных жалоб"""
        return await self.db.complaints.find({"status": ComplaintStatus.PENDING}).sort("created_at", 1).limit(limit).to_list(length=None)

    async def review_complaint(self, complaint_id: str, status: str, admin_id: int, comment: Optional[str] = None) -> bool:
        """Обработать жалобу (reviewed/rejected/resolved)"""
        try:
            await self.db.complaints.update_one(
                {"_id": complaint_id},
                {"$set": {
                    "status": status,
                    "reviewed_by": admin_id,
                    "reviewed_at": datetime.now(UTC),
                    "admin_comment": comment
                }}
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при обработке жалобы: {e}")
            return False

    async def get_complaint_stats(self) -> Dict[str, int]:
        """Статистика по жалобам"""
        try:
            total = await self.db.complaints.count_documents({})
            pending = await self.db.complaints.count_documents({"status": ComplaintStatus.PENDING})
            reviewed = await self.db.complaints.count_documents({"status": ComplaintStatus.REVIEWED})
            rejected = await self.db.complaints.count_documents({"status": ComplaintStatus.REJECTED})
            resolved = await self.db.complaints.count_documents({"status": ComplaintStatus.RESOLVED})
            return {
                "total": total,
                "pending": pending,
                "reviewed": reviewed,
                "rejected": rejected,
                "resolved": resolved
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики жалоб: {e}")
            return {}

    async def get_user_complaints(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить жалобы пользователя"""
        return await self.db.complaints.find({"user_id": user_id}).sort("created_at", -1).limit(limit).to_list(length=None) 