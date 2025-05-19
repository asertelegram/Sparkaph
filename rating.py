import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RatingSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.ratings = db.ratings
        self.levels = db.user_levels

    async def calculate_points(self, user_id: int, action: str, data: Dict[str, Any]) -> int:
        """Расчет очков за действие"""
        points = 0
        try:
            if action == "challenge_complete":
                # Базовые очки за выполнение
                points = 100
                
                # Бонус за скорость выполнения
                if "completion_time" in data:
                    completion_time = data["completion_time"]
                    if completion_time < 3600:  # Менее часа
                        points += 50
                    elif completion_time < 86400:  # Менее суток
                        points += 25
                
                # Бонус за сложность
                if "difficulty" in data:
                    difficulty = data["difficulty"]
                    if difficulty == "hard":
                        points *= 2
                    elif difficulty == "medium":
                        points *= 1.5
                
                # Бонус за серию
                streak = await self.get_user_streak(user_id)
                if streak > 0:
                    points += min(streak * 10, 100)  # Максимум 100 бонусных очков за серию
            
            elif action == "social_share":
                points = 50  # Базовые очки за шеринг
                
                # Бонус за количество лайков
                if "likes" in data:
                    points += min(data["likes"] // 10, 100)  # 1 очко за 10 лайков, максимум 100
            
            elif action == "invite_friend":
                points = 200  # Очки за приглашение друга
            
            # Обновляем рейтинг пользователя
            await self.update_rating(user_id, points)
            
            return points
        except Exception as e:
            logger.error(f"Error calculating points: {e}")
            raise

    async def update_rating(self, user_id: int, points: int) -> None:
        """Обновление рейтинга пользователя"""
        try:
            # Обновляем общий рейтинг
            await self.ratings.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"points": points},
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )
            
            # Проверяем и обновляем уровень
            await self.check_level_up(user_id)
        except Exception as e:
            logger.error(f"Error updating rating: {e}")
            raise

    async def get_user_rating(self, user_id: int) -> Dict[str, Any]:
        """Получение рейтинга пользователя"""
        try:
            rating = await self.ratings.find_one({"user_id": user_id})
            if not rating:
                return {"points": 0, "level": 1, "rank": "Новичок"}
            
            level = await self.levels.find_one({"user_id": user_id})
            if not level:
                level = {"level": 1, "title": "Новичок"}
            
            return {
                "points": rating.get("points", 0),
                "level": level.get("level", 1),
                "title": level.get("title", "Новичок"),
                "updated_at": rating.get("updated_at")
            }
        except Exception as e:
            logger.error(f"Error getting user rating: {e}")
            raise

    async def get_leaderboard(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение таблицы лидеров"""
        try:
            cursor = self.ratings.find().sort("points", -1).limit(limit)
            leaderboard = []
            async for doc in cursor:
                level = await self.levels.find_one({"user_id": doc["user_id"]})
                leaderboard.append({
                    "user_id": doc["user_id"],
                    "points": doc["points"],
                    "level": level.get("level", 1) if level else 1,
                    "title": level.get("title", "Новичок") if level else "Новичок"
                })
            return leaderboard
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            raise

    async def check_level_up(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Проверка повышения уровня"""
        try:
            rating = await self.get_user_rating(user_id)
            current_level = rating["level"]
            points = rating["points"]
            
            # Формула для расчета уровня: level = 1 + (points // 1000)
            new_level = 1 + (points // 1000)
            
            if new_level > current_level:
                # Определяем титул на основе уровня
                title = self._get_level_title(new_level)
                
                # Обновляем уровень
                await self.levels.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "level": new_level,
                            "title": title,
                            "updated_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                
                return {
                    "old_level": current_level,
                    "new_level": new_level,
                    "title": title
                }
            return None
        except Exception as e:
            logger.error(f"Error checking level up: {e}")
            raise

    def _get_level_title(self, level: int) -> str:
        """Получение титула на основе уровня"""
        if level >= 20:
            return "Легенда"
        elif level >= 15:
            return "Мастер"
        elif level >= 10:
            return "Эксперт"
        elif level >= 5:
            return "Опытный"
        else:
            return "Новичок"

    async def get_user_streak(self, user_id: int) -> int:
        """Получение текущей серии пользователя"""
        try:
            # Получаем последние выполнения челленджей
            completions = await self.db.challenge_participants.find({
                "participants": user_id,
                "completions": {"$exists": True}
            }).sort("completions.completed_at", -1).limit(1).to_list(length=1)
            
            if not completions:
                return 0
            
            # Проверяем, был ли челлендж выполнен сегодня
            last_completion = completions[0]["completions"][str(user_id)]["completed_at"]
            if (datetime.utcnow() - last_completion).days > 1:
                return 0
            
            # Получаем текущую серию
            streak = await self.db.user_streaks.find_one({"user_id": user_id})
            return streak.get("current_streak", 0) if streak else 0
        except Exception as e:
            logger.error(f"Error getting user streak: {e}")
            raise 