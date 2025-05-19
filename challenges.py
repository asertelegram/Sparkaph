import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChallengeStatus:
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class Challenge:
    def __init__(
        self,
        title: str,
        description: str,
        creator_id: int,
        start_date: datetime,
        end_date: datetime,
        requirements: Dict[str, Any],
        rewards: Dict[str, Any],
        max_participants: Optional[int] = None,
        category: str = "general"
    ):
        self.id = str(ObjectId())
        self.title = title
        self.description = description
        self.creator_id = creator_id
        self.start_date = start_date
        self.end_date = end_date
        self.requirements = requirements
        self.rewards = rewards
        self.max_participants = max_participants
        self.category = category
        self.status = ChallengeStatus.ACTIVE
        self.participants = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

class ChallengeManager:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.challenges = db.challenges
        self.participants = db.challenge_participants

    async def create_challenge(self, challenge: Challenge) -> str:
        """Создание нового челленджа"""
        try:
            result = await self.challenges.insert_one(challenge.__dict__)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            raise

    async def get_challenge(self, challenge_id: str) -> Optional[Challenge]:
        """Получение челленджа по ID"""
        try:
            challenge_data = await self.challenges.find_one({"_id": ObjectId(challenge_id)})
            if challenge_data:
                return Challenge(**challenge_data)
            return None
        except Exception as e:
            logger.error(f"Error getting challenge: {e}")
            raise

    async def update_challenge(self, challenge_id: str, update_data: Dict[str, Any]) -> bool:
        """Обновление челленджа"""
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = await self.challenges.update_one(
                {"_id": ObjectId(challenge_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating challenge: {e}")
            raise

    async def delete_challenge(self, challenge_id: str) -> bool:
        """Удаление челленджа"""
        try:
            result = await self.challenges.delete_one({"_id": ObjectId(challenge_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting challenge: {e}")
            raise

    async def add_participant(self, challenge_id: str, user_id: int) -> bool:
        """Добавление участника в челлендж"""
        try:
            challenge = await self.get_challenge(challenge_id)
            if not challenge:
                return False

            if challenge.max_participants and len(challenge.participants) >= challenge.max_participants:
                return False

            result = await self.participants.update_one(
                {"challenge_id": challenge_id},
                {"$addToSet": {"participants": user_id}},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error adding participant: {e}")
            raise

    async def remove_participant(self, challenge_id: str, user_id: int) -> bool:
        """Удаление участника из челленджа"""
        try:
            result = await self.participants.update_one(
                {"challenge_id": challenge_id},
                {"$pull": {"participants": user_id}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error removing participant: {e}")
            raise

    async def check_completion(self, challenge_id: str, user_id: int, submission: Dict[str, Any]) -> bool:
        """Проверка выполнения челленджа"""
        try:
            challenge = await self.get_challenge(challenge_id)
            if not challenge:
                return False

            # Проверка требований
            for req_key, req_value in challenge.requirements.items():
                if req_key not in submission or submission[req_key] != req_value:
                    return False

            # Обновление статуса участника
            await self.participants.update_one(
                {
                    "challenge_id": challenge_id,
                    "participants": user_id
                },
                {
                    "$set": {
                        f"completions.{user_id}": {
                            "completed_at": datetime.utcnow(),
                            "submission": submission
                        }
                    }
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error checking completion: {e}")
            raise

    async def get_active_challenges(self) -> List[Challenge]:
        """Получение активных челленджей"""
        try:
            now = datetime.utcnow()
            cursor = self.challenges.find({
                "start_date": {"$lte": now},
                "end_date": {"$gt": now},
                "status": ChallengeStatus.ACTIVE
            })
            return [Challenge(**doc) async for doc in cursor]
        except Exception as e:
            logger.error(f"Error getting active challenges: {e}")
            raise

    async def get_user_challenges(self, user_id: int) -> List[Challenge]:
        """Получение челленджей пользователя"""
        try:
            participant_challenges = await self.participants.find(
                {"participants": user_id}
            ).to_list(length=None)
            
            challenge_ids = [p["challenge_id"] for p in participant_challenges]
            cursor = self.challenges.find({"_id": {"$in": [ObjectId(cid) for cid in challenge_ids]}})
            return [Challenge(**doc) async for doc in cursor]
        except Exception as e:
            logger.error(f"Error getting user challenges: {e}")
            raise 