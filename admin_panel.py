import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdminPanel:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users = db.users
        self.challenges = db.challenges
        self.analytics = db.analytics
        self.reports = db.reports

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики пользователя"""
        try:
            user = await self.users.find_one({"user_id": user_id})
            if not user:
                return {"error": "User not found"}

            # Получаем выполненные челленджи
            completed_challenges = await self.challenges.count_documents({
                "participants": user_id,
                "status": "completed"
            })

            # Получаем активные челленджи
            active_challenges = await self.challenges.count_documents({
                "participants": user_id,
                "status": "active"
            })

            # Получаем рейтинг
            rating = await self.db.ratings.find_one({"user_id": user_id})

            return {
                "user_id": user_id,
                "username": user.get("username"),
                "joined_at": user.get("created_at"),
                "completed_challenges": completed_challenges,
                "active_challenges": active_challenges,
                "rating": rating.get("points", 0) if rating else 0,
                "level": rating.get("level", 1) if rating else 1
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            raise

    async def get_challenge_stats(self, challenge_id: str) -> Dict[str, Any]:
        """Получение статистики челленджа"""
        try:
            challenge = await self.challenges.find_one({"_id": ObjectId(challenge_id)})
            if not challenge:
                return {"error": "Challenge not found"}

            # Получаем количество участников
            participants_count = len(challenge.get("participants", []))

            # Получаем количество выполненных
            completed_count = await self.challenges.count_documents({
                "_id": ObjectId(challenge_id),
                "status": "completed"
            })

            # Получаем среднее время выполнения
            completions = await self.db.challenge_participants.find({
                "challenge_id": challenge_id,
                "completions": {"$exists": True}
            }).to_list(length=None)

            avg_completion_time = 0
            if completions:
                total_time = sum(
                    (c["completions"][str(p)]["completed_at"] - challenge["start_date"]).total_seconds()
                    for c in completions
                    for p in c["participants"]
                )
                avg_completion_time = total_time / len(completions)

            return {
                "challenge_id": challenge_id,
                "title": challenge.get("title"),
                "created_at": challenge.get("created_at"),
                "participants_count": participants_count,
                "completed_count": completed_count,
                "completion_rate": (completed_count / participants_count * 100) if participants_count > 0 else 0,
                "avg_completion_time": avg_completion_time
            }
        except Exception as e:
            logger.error(f"Error getting challenge stats: {e}")
            raise

    async def generate_analytics_report(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Генерация аналитического отчета"""
        try:
            # Статистика пользователей
            new_users = await self.users.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            })

            active_users = await self.users.count_documents({
                "last_active": {"$gte": start_date, "$lte": end_date}
            })

            # Статистика челленджей
            new_challenges = await self.challenges.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            })

            completed_challenges = await self.challenges.count_documents({
                "status": "completed",
                "updated_at": {"$gte": start_date, "$lte": end_date}
            })

            # Сохраняем отчет
            report = {
                "period": {
                    "start": start_date,
                    "end": end_date
                },
                "users": {
                    "new": new_users,
                    "active": active_users
                },
                "challenges": {
                    "new": new_challenges,
                    "completed": completed_challenges
                },
                "generated_at": datetime.utcnow()
            }

            await self.reports.insert_one(report)
            return report
        except Exception as e:
            logger.error(f"Error generating analytics report: {e}")
            raise

    async def manage_user(self, user_id: int, action: str, data: Dict[str, Any]) -> bool:
        """Управление пользователем"""
        try:
            if action == "ban":
                await self.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "is_banned": True,
                            "ban_reason": data.get("reason"),
                            "banned_at": datetime.utcnow()
                        }
                    }
                )
            elif action == "unban":
                await self.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "is_banned": False,
                            "ban_reason": None,
                            "banned_at": None
                        }
                    }
                )
            elif action == "update_role":
                await self.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"role": data.get("role")}}
                )
            else:
                return False

            return True
        except Exception as e:
            logger.error(f"Error managing user: {e}")
            raise

    async def manage_challenge(self, challenge_id: str, action: str, data: Dict[str, Any]) -> bool:
        """Управление челленджем"""
        try:
            if action == "update":
                await self.challenges.update_one(
                    {"_id": ObjectId(challenge_id)},
                    {"$set": data}
                )
            elif action == "delete":
                await self.challenges.delete_one({"_id": ObjectId(challenge_id)})
            elif action == "cancel":
                await self.challenges.update_one(
                    {"_id": ObjectId(challenge_id)},
                    {"$set": {"status": "cancelled"}}
                )
            else:
                return False

            return True
        except Exception as e:
            logger.error(f"Error managing challenge: {e}")
            raise

    async def get_system_analytics(self) -> Dict[str, Any]:
        """Получение системной аналитики"""
        try:
            # Общая статистика
            total_users = await self.users.count_documents({})
            total_challenges = await self.challenges.count_documents({})
            active_challenges = await self.challenges.count_documents({"status": "active"})

            # Статистика по категориям
            category_stats = {}
            async for doc in self.challenges.aggregate([
                {"$group": {"_id": "$category", "count": {"$sum": 1}}}
            ]):
                category_stats[doc["_id"]] = doc["count"]

            # Статистика по уровням пользователей
            level_stats = {}
            async for doc in self.db.ratings.aggregate([
                {"$group": {"_id": "$level", "count": {"$sum": 1}}}
            ]):
                level_stats[doc["_id"]] = doc["count"]

            return {
                "total_users": total_users,
                "total_challenges": total_challenges,
                "active_challenges": active_challenges,
                "category_stats": category_stats,
                "level_stats": level_stats,
                "generated_at": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error getting system analytics: {e}")
            raise

# Создаем глобальный экземпляр админ-панели
admin_panel = None

def init_admin_panel(db: AsyncIOMotorDatabase) -> None:
    """Инициализация админ-панели"""
    global admin_panel
    admin_panel = AdminPanel(db) 