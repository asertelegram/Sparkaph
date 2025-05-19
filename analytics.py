import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyticsSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def log_event(self, user_id: int, event: str, data: Optional[Dict[str, Any]] = None):
        try:
            await self.db.analytics.insert_one({
                "user_id": user_id,
                "event": event,
                "data": data or {},
                "timestamp": datetime.now(UTC)
            })
        except Exception as e:
            logger.error(f"Ошибка при логировании события аналитики: {e}")

    async def get_user_events(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        return await self.db.analytics.find({"user_id": user_id}).sort("timestamp", -1).limit(limit).to_list(length=None)

    async def get_event_stats(self, event: str) -> Dict[str, Any]:
        try:
            count = await self.db.analytics.count_documents({"event": event})
            return {"event": event, "count": count}
        except Exception as e:
            logger.error(f"Ошибка при получении статистики события: {e}")
            return {}

    async def get_global_stats(self) -> Dict[str, Any]:
        try:
            total = await self.db.analytics.count_documents({})
            events = await self.db.analytics.aggregate([
                {"$group": {"_id": "$event", "count": {"$sum": 1}}}
            ]).to_list(length=None)
            return {
                "total": total,
                "by_event": {e["_id"]: e["count"] for e in events}
            }
        except Exception as e:
            logger.error(f"Ошибка при получении глобальной статистики: {e}")
            return {} 