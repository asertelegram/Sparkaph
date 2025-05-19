import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertStatus:
    NEW = "new"
    ACK = "acknowledged"
    RESOLVED = "resolved"

class AlertSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create_alert(self, alert_type: str, message: str, severity: str = "info", data: Optional[Dict[str, Any]] = None) -> bool:
        try:
            await self.db.alerts.insert_one({
                "type": alert_type,
                "message": message,
                "severity": severity,
                "data": data or {},
                "status": AlertStatus.NEW,
                "created_at": datetime.now(UTC)
            })
            return True
        except Exception as e:
            logger.error(f"Ошибка при создании алерта: {e}")
            return False

    async def get_alerts(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = {}
        if status:
            query["status"] = status
        return await self.db.alerts.find(query).sort("created_at", -1).limit(limit).to_list(length=None)

    async def update_alert_status(self, alert_id: str, status: str) -> bool:
        try:
            await self.db.alerts.update_one({"_id": alert_id}, {"$set": {"status": status, "updated_at": datetime.now(UTC)}})
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса алерта: {e}")
            return False

    async def get_alert_stats(self) -> Dict[str, int]:
        try:
            total = await self.db.alerts.count_documents({})
            new = await self.db.alerts.count_documents({"status": AlertStatus.NEW})
            ack = await self.db.alerts.count_documents({"status": AlertStatus.ACK})
            resolved = await self.db.alerts.count_documents({"status": AlertStatus.RESOLVED})
            return {
                "total": total,
                "new": new,
                "acknowledged": ack,
                "resolved": resolved
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики алертов: {e}")
            return {} 