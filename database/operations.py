from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from .models import User, Challenge, VideoSubmission, LeaderboardEntry, Notification
from config import MONGODB_URI, DATABASE_NAME

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DATABASE_NAME]
        
        # Коллекции
        self.users = self.db.users
        self.challenges = self.db.challenges
        self.submissions = self.db.submissions
        self.leaderboard = self.db.leaderboard
        self.notifications = self.db.notifications
        self.error_logs = self.db.error_logs
        self.stats = self.db.stats

    # Операции с пользователями
    async def get_user(self, user_id: int) -> Optional[User]:
        user_data = await self.users.find_one({"user_id": user_id})
        return User(**user_data) if user_data else None

    async def create_user(self, user: User) -> None:
        await self.users.insert_one(user.dict())

    async def update_user(self, user_id: int, update_data: Dict[str, Any]) -> None:
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )

    # Операции с челленджами
    async def get_challenge(self, challenge_id: int) -> Optional[Challenge]:
        challenge_data = await self.challenges.find_one({"challenge_id": challenge_id})
        return Challenge(**challenge_data) if challenge_data else None

    async def get_active_challenges(self, category: Optional[str] = None) -> List[Challenge]:
        query = {"is_active": True}
        if category:
            query["category"] = category
        
        cursor = self.challenges.find(query)
        return [Challenge(**doc) async for doc in cursor]

    async def create_challenge(self, challenge: Challenge) -> None:
        await self.challenges.insert_one(challenge.dict())

    # Операции с видео
    async def create_submission(self, submission: VideoSubmission) -> None:
        await self.submissions.insert_one(submission.dict())

    async def get_pending_submissions(self) -> List[VideoSubmission]:
        cursor = self.submissions.find({"status": "pending"})
        return [VideoSubmission(**doc) async for doc in cursor]

    async def update_submission_status(
        self,
        submission_id: int,
        status: str,
        moderator_id: Optional[int] = None,
        rejection_reason: Optional[str] = None
    ) -> None:
        update_data = {
            "status": status,
            "moderated_at": datetime.utcnow(),
            "moderator_id": moderator_id
        }
        if rejection_reason:
            update_data["rejection_reason"] = rejection_reason

        await self.submissions.update_one(
            {"submission_id": submission_id},
            {"$set": update_data}
        )

    # Операции с лидербордом
    async def update_leaderboard(self, user_id: int, points: int) -> None:
        await self.leaderboard.update_one(
            {"user_id": user_id},
            {
                "$inc": {"points": points},
                "$set": {"last_updated": datetime.utcnow()}
            },
            upsert=True
        )

    async def get_top_users(self, limit: int = 10) -> List[LeaderboardEntry]:
        cursor = self.leaderboard.find().sort("points", -1).limit(limit)
        return [LeaderboardEntry(**doc) async for doc in cursor]

    # Операции с уведомлениями
    async def create_notification(self, notification: Notification) -> None:
        await self.notifications.insert_one(notification.dict())

    async def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False
    ) -> List[Notification]:
        query = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False

        cursor = self.notifications.find(query).sort("created_at", -1)
        return [Notification(**doc) async for doc in cursor]

    async def mark_notification_as_read(self, notification_id: str) -> None:
        await self.notifications.update_one(
            {"_id": notification_id},
            {"$set": {"is_read": True}}
        )

    # Статистика
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        user = await self.get_user(user_id)
        if not user:
            return {}

        completed_challenges = len(user.completed_challenges)
        submissions = await self.submissions.count_documents({"user_id": user_id})
        approved_submissions = await self.submissions.count_documents({
            "user_id": user_id,
            "status": "approved"
        })

        return {
            "completed_challenges": completed_challenges,
            "total_submissions": submissions,
            "approved_submissions": approved_submissions,
            "streak_days": user.streak_days,
            "badges": user.badges
        }

    async def get_challenge_stats(self, challenge_id: int) -> Dict[str, Any]:
        challenge = await self.get_challenge(challenge_id)
        if not challenge:
            return {}

        submissions = await self.submissions.count_documents({"challenge_id": challenge_id})
        approved_submissions = await self.submissions.count_documents({
            "challenge_id": challenge_id,
            "status": "approved"
        })

        return {
            "views": challenge.views_count,
            "completions": challenge.completions_count,
            "submissions": submissions,
            "approved_submissions": approved_submissions
        }

    # Новые методы для работы с ошибками
    async def create_error_log(self, error_data: dict) -> None:
        """Создает запись об ошибке."""
        error_data['created_at'] = datetime.utcnow()
        await self.error_logs.insert_one(error_data)

    async def get_error_logs(self, limit: int = 100) -> List[dict]:
        """Получает последние записи об ошибках."""
        cursor = self.error_logs.find().sort('created_at', -1).limit(limit)
        return [doc async for doc in cursor]

    # Новые методы для работы со статистикой
    async def update_submission_stats(
        self,
        submission_id: int,
        views_count: int,
        likes_count: int
    ) -> None:
        """Обновляет статистику видео."""
        await self.submissions.update_one(
            {"submission_id": submission_id},
            {
                "$set": {
                    "views_count": views_count,
                    "likes_count": likes_count,
                    "last_updated": datetime.utcnow()
                }
            }
        )

    async def get_user_activity_stats(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Получает статистику активности пользователя."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        submissions = await self.submissions.count_documents({
            "user_id": user_id,
            "submitted_at": {"$gte": start_date}
        })
        
        approved_submissions = await self.submissions.count_documents({
            "user_id": user_id,
            "status": "approved",
            "submitted_at": {"$gte": start_date}
        })
        
        total_views = await self.submissions.aggregate([
            {"$match": {
                "user_id": user_id,
                "submitted_at": {"$gte": start_date}
            }},
            {"$group": {
                "_id": None,
                "total_views": {"$sum": "$views_count"},
                "total_likes": {"$sum": "$likes_count"}
            }}
        ]).to_list(1)
        
        return {
            "submissions": submissions,
            "approved_submissions": approved_submissions,
            "total_views": total_views[0]["total_views"] if total_views else 0,
            "total_likes": total_views[0]["total_likes"] if total_views else 0
        }

    async def get_challenge_activity_stats(
        self,
        challenge_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Получает статистику активности челленджа."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        submissions = await self.submissions.count_documents({
            "challenge_id": challenge_id,
            "submitted_at": {"$gte": start_date}
        })
        
        approved_submissions = await self.submissions.count_documents({
            "challenge_id": challenge_id,
            "status": "approved",
            "submitted_at": {"$gte": start_date}
        })
        
        total_views = await self.submissions.aggregate([
            {"$match": {
                "challenge_id": challenge_id,
                "submitted_at": {"$gte": start_date}
            }},
            {"$group": {
                "_id": None,
                "total_views": {"$sum": "$views_count"},
                "total_likes": {"$sum": "$likes_count"}
            }}
        ]).to_list(1)
        
        return {
            "submissions": submissions,
            "approved_submissions": approved_submissions,
            "total_views": total_views[0]["total_views"] if total_views else 0,
            "total_likes": total_views[0]["total_likes"] if total_views else 0
        }

    async def get_global_stats(self) -> Dict[str, Any]:
        """Получает глобальную статистику."""
        total_users = await self.users.count_documents({})
        total_challenges = await self.challenges.count_documents({})
        total_submissions = await self.submissions.count_documents({})
        total_approved = await self.submissions.count_documents({"status": "approved"})
        
        total_views = await self.submissions.aggregate([
            {"$group": {
                "_id": None,
                "total_views": {"$sum": "$views_count"},
                "total_likes": {"$sum": "$likes_count"}
            }}
        ]).to_list(1)
        
        return {
            "total_users": total_users,
            "total_challenges": total_challenges,
            "total_submissions": total_submissions,
            "total_approved": total_approved,
            "total_views": total_views[0]["total_views"] if total_views else 0,
            "total_likes": total_views[0]["total_likes"] if total_views else 0
        }

    async def update_global_stats(self) -> None:
        """Обновляет глобальную статистику."""
        stats = await self.get_global_stats()
        stats['updated_at'] = datetime.utcnow()
        
        await self.stats.update_one(
            {"_id": "global"},
            {"$set": stats},
            upsert=True
        ) 