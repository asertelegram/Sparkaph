import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuditSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def log_action(self, user_id: int, action: str, details: Optional[Dict[str, Any]] = None, role: Optional[str] = None):
        try:
            await self.db.audit_logs.insert_one({
                "user_id": user_id,
                "action": action,
                "details": details or {},
                "role": role,
                "timestamp": datetime.now(UTC)
            })
        except Exception as e:
            logger.error(f"Ошибка при логировании действия: {e}")

    async def get_logs(self, user_id: Optional[int] = None, action: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = {}
        if user_id:
            query["user_id"] = user_id
        if action:
            query["action"] = action
        return await self.db.audit_logs.find(query).sort("timestamp", -1).limit(limit).to_list(length=None)

    async def get_stats(self) -> Dict[str, int]:
        try:
            total = await self.db.audit_logs.count_documents({})
            actions = await self.db.audit_logs.aggregate([
                {"$group": {"_id": "$action", "count": {"$sum": 1}}}
            ]).to_list(length=None)
            return {
                "total": total,
                "by_action": {a["_id"]: a["count"] for a in actions}
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики аудита: {e}")
            return {} 