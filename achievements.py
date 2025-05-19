import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, UTC, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AchievementType(Enum):
    CHALLENGE = "challenge"  # Достижения за выполнение челленджей
    STREAK = "streak"  # Достижения за серии
    SOCIAL = "social"  # Достижения за социальную активность
    LEVEL = "level"  # Достижения за уровни
    SPECIAL = "special"  # Специальные достижения
    COLLECTION = "collection"  # Достижения за коллекции
    EVENT = "event"  # Достижения за события

@dataclass
class Achievement:
    id: str
    name: str
    description: str
    type: AchievementType
    points: int
    icon: str
    requirements: Dict[str, Any]
    rewards: Dict[str, Any]
    is_hidden: bool = False
    is_seasonal: bool = False
    season: Optional[str] = None
    expires_at: Optional[datetime] = None

class AchievementSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.achievements: Dict[str, Achievement] = {}
        self._load_achievements()
    
    def _load_achievements(self):
        """Загрузка всех достижений"""
        # Достижения за челленджи
        self.achievements.update({
            "first_challenge": Achievement(
                id="first_challenge",
                name="🎯 Первый шаг",
                description="Выполнил свой первый челлендж",
                type=AchievementType.CHALLENGE,
                points=10,
                icon="🎯",
                requirements={"challenges_completed": 1},
                rewards={"points": 10, "badge": "first_challenge"}
            ),
            "challenge_master": Achievement(
                id="challenge_master",
                name="🏆 Мастер челленджей",
                description="Выполнил 50 челленджей",
                type=AchievementType.CHALLENGE,
                points=50,
                icon="🏆",
                requirements={"challenges_completed": 50},
                rewards={"points": 50, "badge": "challenge_master", "title": "Мастер"}
            ),
            "challenge_legend": Achievement(
                id="challenge_legend",
                name="👑 Легенда",
                description="Выполнил 100 челленджей",
                type=AchievementType.CHALLENGE,
                points=100,
                icon="👑",
                requirements={"challenges_completed": 100},
                rewards={"points": 100, "badge": "challenge_legend", "title": "Легенда"}
            )
        })
        
        # Достижения за серии
        self.achievements.update({
            "streak_3": Achievement(
                id="streak_3",
                name="🔥 Горячая серия",
                description="3 дня подряд выполнял челленджи",
                type=AchievementType.STREAK,
                points=15,
                icon="🔥",
                requirements={"streak_days": 3},
                rewards={"points": 15, "badge": "streak_3"}
            ),
            "streak_7": Achievement(
                id="streak_7",
                name="⚡ Неделя силы",
                description="7 дней подряд выполнял челленджи",
                type=AchievementType.STREAK,
                points=30,
                icon="⚡",
                requirements={"streak_days": 7},
                rewards={"points": 30, "badge": "streak_7", "bonus": "double_points_24h"}
            ),
            "streak_30": Achievement(
                id="streak_30",
                name="🌟 Месяц силы",
                description="30 дней подряд выполнял челленджи",
                type=AchievementType.STREAK,
                points=100,
                icon="🌟",
                requirements={"streak_days": 30},
                rewards={"points": 100, "badge": "streak_30", "title": "Неутомимый", "bonus": "triple_points_24h"}
            )
        })
        
        # Достижения за социальную активность
        self.achievements.update({
            "social_butterfly": Achievement(
                id="social_butterfly",
                name="🦋 Социальная бабочка",
                description="Пригласил 5 друзей",
                type=AchievementType.SOCIAL,
                points=25,
                icon="🦋",
                requirements={"referrals": 5},
                rewards={"points": 25, "badge": "social_butterfly"}
            ),
            "social_queen": Achievement(
                id="social_queen",
                name="👑 Королева соцсетей",
                description="Пригласил 20 друзей",
                type=AchievementType.SOCIAL,
                points=50,
                icon="👑",
                requirements={"referrals": 20},
                rewards={"points": 50, "badge": "social_queen", "title": "Социальный лидер"}
            ),
            "content_creator": Achievement(
                id="content_creator",
                name="📱 Контент-мейкер",
                description="Поделился 10 челленджами в соцсетях",
                type=AchievementType.SOCIAL,
                points=30,
                icon="📱",
                requirements={"social_shares": 10},
                rewards={"points": 30, "badge": "content_creator"}
            )
        })
        
        # Достижения за уровни
        self.achievements.update({
            "level_5": Achievement(
                id="level_5",
                name="⭐️ Пятый уровень",
                description="Достиг 5 уровня",
                type=AchievementType.LEVEL,
                points=20,
                icon="⭐️",
                requirements={"level": 5},
                rewards={"points": 20, "badge": "level_5"}
            ),
            "level_10": Achievement(
                id="level_10",
                name="🌟 Десятый уровень",
                description="Достиг 10 уровня",
                type=AchievementType.LEVEL,
                points=50,
                icon="🌟",
                requirements={"level": 10},
                rewards={"points": 50, "badge": "level_10", "title": "Опытный"}
            ),
            "level_20": Achievement(
                id="level_20",
                name="👑 Двадцатый уровень",
                description="Достиг 20 уровня",
                type=AchievementType.LEVEL,
                points=100,
                icon="👑",
                requirements={"level": 20},
                rewards={"points": 100, "badge": "level_20", "title": "Мастер"}
            )
        })
        
        # Специальные достижения
        self.achievements.update({
            "early_bird": Achievement(
                id="early_bird",
                name="🌅 Ранняя пташка",
                description="Выполнил челлендж до 8 утра",
                type=AchievementType.SPECIAL,
                points=15,
                icon="🌅",
                requirements={"early_completion": 1},
                rewards={"points": 15, "badge": "early_bird"}
            ),
            "night_owl": Achievement(
                id="night_owl",
                name="🦉 Ночная сова",
                description="Выполнил челлендж после 10 вечера",
                type=AchievementType.SPECIAL,
                points=15,
                icon="🦉",
                requirements={"late_completion": 1},
                rewards={"points": 15, "badge": "night_owl"}
            ),
            "perfect_week": Achievement(
                id="perfect_week",
                name="✨ Идеальная неделя",
                description="Выполнил все челленджи за неделю",
                type=AchievementType.SPECIAL,
                points=50,
                icon="✨",
                requirements={"weekly_completion": 7},
                rewards={"points": 50, "badge": "perfect_week", "bonus": "double_points_week"}
            )
        })
        
        # Достижения за коллекции
        self.achievements.update({
            "collection_starter": Achievement(
                id="collection_starter",
                name="📚 Начинающий коллекционер",
                description="Собрал 5 бейджей",
                type=AchievementType.COLLECTION,
                points=20,
                icon="📚",
                requirements={"badges_collected": 5},
                rewards={"points": 20, "badge": "collection_starter"}
            ),
            "collection_master": Achievement(
                id="collection_master",
                name="🏆 Мастер коллекций",
                description="Собрал 20 бейджей",
                type=AchievementType.COLLECTION,
                points=50,
                icon="🏆",
                requirements={"badges_collected": 20},
                rewards={"points": 50, "badge": "collection_master", "title": "Коллекционер"}
            )
        })
        
        # Сезонные достижения
        self.achievements.update({
            "summer_champion": Achievement(
                id="summer_champion",
                name="☀️ Летний чемпион",
                description="Выполнил 30 челленджей летом",
                type=AchievementType.EVENT,
                points=100,
                icon="☀️",
                requirements={"seasonal_challenges": 30},
                rewards={"points": 100, "badge": "summer_champion", "title": "Летний чемпион"},
                is_seasonal=True,
                season="summer",
                expires_at=datetime(2024, 9, 1, tzinfo=UTC)
            ),
            "winter_warrior": Achievement(
                id="winter_warrior",
                name="❄️ Зимний воин",
                description="Выполнил 30 челленджей зимой",
                type=AchievementType.EVENT,
                points=100,
                icon="❄️",
                requirements={"seasonal_challenges": 30},
                rewards={"points": 100, "badge": "winter_warrior", "title": "Зимний воин"},
                is_seasonal=True,
                season="winter",
                expires_at=datetime(2024, 3, 1, tzinfo=UTC)
            )
        })
    
    async def check_achievements(self, user: Dict[str, Any]) -> List[Achievement]:
        """Проверка достижений пользователя"""
        new_achievements = []
        
        # Получаем текущие достижения пользователя
        user_achievements = set(user.get("achievements", []))
        
        # Проверяем каждое достижение
        for achievement in self.achievements.values():
            # Пропускаем уже полученные достижения
            if achievement.id in user_achievements:
                continue
            
            # Пропускаем скрытые достижения
            if achievement.is_hidden:
                continue
            
            # Пропускаем сезонные достижения не в сезон
            if achievement.is_seasonal:
                if not self._is_season_active(achievement.season):
                    continue
                if achievement.expires_at and datetime.now(UTC) > achievement.expires_at:
                    continue
            
            # Проверяем требования
            if self._check_requirements(user, achievement.requirements):
                new_achievements.append(achievement)
        
        return new_achievements
    
    def _check_requirements(self, user: Dict[str, Any], requirements: Dict[str, Any]) -> bool:
        """Проверка требований достижения"""
        for key, value in requirements.items():
            if key == "challenges_completed":
                if len(user.get("completed_challenges", [])) < value:
                    return False
            elif key == "streak_days":
                if user.get("streak", 0) < value:
                    return False
            elif key == "referrals":
                if len(user.get("referrals", [])) < value:
                    return False
            elif key == "social_shares":
                if len(user.get("social_shares", [])) < value:
                    return False
            elif key == "level":
                if user.get("level", 0) < value:
                    return False
            elif key == "early_completion":
                if not self._has_early_completion(user):
                    return False
            elif key == "late_completion":
                if not self._has_late_completion(user):
                    return False
            elif key == "weekly_completion":
                if not self._has_weekly_completion(user, value):
                    return False
            elif key == "badges_collected":
                if len(user.get("badges", [])) < value:
                    return False
            elif key == "seasonal_challenges":
                if not self._has_seasonal_challenges(user, value):
                    return False
        
        return True
    
    def _is_season_active(self, season: str) -> bool:
        """Проверка активного сезона"""
        now = datetime.now(UTC)
        month = now.month
        
        if season == "summer":
            return 6 <= month <= 8
        elif season == "winter":
            return 12 <= month <= 2
        elif season == "spring":
            return 3 <= month <= 5
        elif season == "autumn":
            return 9 <= month <= 11
        
        return False
    
    def _has_early_completion(self, user: Dict[str, Any]) -> bool:
        """Проверка раннего выполнения челленджа"""
        for challenge in user.get("completed_challenges", []):
            completion_time = challenge.get("completed_at")
            if completion_time and completion_time.hour < 8:
                return True
        return False
    
    def _has_late_completion(self, user: Dict[str, Any]) -> bool:
        """Проверка позднего выполнения челленджа"""
        for challenge in user.get("completed_challenges", []):
            completion_time = challenge.get("completed_at")
            if completion_time and completion_time.hour >= 22:
                return True
        return False
    
    def _has_weekly_completion(self, user: Dict[str, Any], days: int) -> bool:
        """Проверка выполнения челленджей за неделю"""
        now = datetime.now(UTC)
        week_start = now - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=7)
        
        completed_days = set()
        for challenge in user.get("completed_challenges", []):
            completion_time = challenge.get("completed_at")
            if completion_time and week_start <= completion_time < week_end:
                completed_days.add(completion_time.date())
        
        return len(completed_days) >= days
    
    def _has_seasonal_challenges(self, user: Dict[str, Any], count: int) -> bool:
        """Проверка выполнения сезонных челленджей"""
        now = datetime.now(UTC)
        season_start = self._get_season_start(now)
        season_end = self._get_season_end(now)
        
        completed_count = 0
        for challenge in user.get("completed_challenges", []):
            completion_time = challenge.get("completed_at")
            if completion_time and season_start <= completion_time < season_end:
                completed_count += 1
        
        return completed_count >= count
    
    def _get_season_start(self, date: datetime) -> datetime:
        """Получение начала сезона"""
        month = date.month
        if 3 <= month <= 5:  # Весна
            return datetime(date.year, 3, 1, tzinfo=UTC)
        elif 6 <= month <= 8:  # Лето
            return datetime(date.year, 6, 1, tzinfo=UTC)
        elif 9 <= month <= 11:  # Осень
            return datetime(date.year, 9, 1, tzinfo=UTC)
        else:  # Зима
            return datetime(date.year, 12, 1, tzinfo=UTC)
    
    def _get_season_end(self, date: datetime) -> datetime:
        """Получение конца сезона"""
        month = date.month
        if 3 <= month <= 5:  # Весна
            return datetime(date.year, 6, 1, tzinfo=UTC)
        elif 6 <= month <= 8:  # Лето
            return datetime(date.year, 9, 1, tzinfo=UTC)
        elif 9 <= month <= 11:  # Осень
            return datetime(date.year, 12, 1, tzinfo=UTC)
        else:  # Зима
            return datetime(date.year + 1, 3, 1, tzinfo=UTC)
    
    async def award_achievement(self, user_id: int, achievement: Achievement) -> bool:
        """Выдача достижения пользователю"""
        try:
            # Обновляем достижения пользователя
            await self.db.users.update_one(
                {"user_id": user_id},
                {
                    "$push": {"achievements": achievement.id},
                    "$inc": {"points": achievement.points}
                }
            )
            
            # Добавляем бейдж, если есть
            if "badge" in achievement.rewards:
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {"$push": {"badges": achievement.rewards["badge"]}}
                )
            
            # Добавляем титул, если есть
            if "title" in achievement.rewards:
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"title": achievement.rewards["title"]}}
                )
            
            # Добавляем бонус, если есть
            if "bonus" in achievement.rewards:
                await self._apply_bonus(user_id, achievement.rewards["bonus"])
            
            # Логируем выдачу достижения
            await self.db.achievement_logs.insert_one({
                "user_id": user_id,
                "achievement_id": achievement.id,
                "awarded_at": datetime.now(UTC),
                "points": achievement.points,
                "rewards": achievement.rewards
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при выдаче достижения: {e}")
            return False
    
    async def _apply_bonus(self, user_id: int, bonus: str):
        """Применение бонуса"""
        try:
            if bonus == "double_points_24h":
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "bonus_double_points": True,
                            "bonus_expires_at": datetime.now(UTC) + timedelta(hours=24)
                        }
                    }
                )
            elif bonus == "triple_points_24h":
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "bonus_triple_points": True,
                            "bonus_expires_at": datetime.now(UTC) + timedelta(hours=24)
                        }
                    }
                )
            elif bonus == "double_points_week":
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "bonus_double_points": True,
                            "bonus_expires_at": datetime.now(UTC) + timedelta(days=7)
                        }
                    }
                )
        except Exception as e:
            logger.error(f"Ошибка при применении бонуса: {e}")
    
    async def get_user_achievements(self, user: Dict[str, Any]) -> List[Achievement]:
        """Получение достижений пользователя"""
        user_achievements = []
        for achievement_id in user.get("achievements", []):
            if achievement_id in self.achievements:
                user_achievements.append(self.achievements[achievement_id])
        return user_achievements
    
    async def get_available_achievements(self, user: Dict[str, Any]) -> List[Achievement]:
        """Получение доступных достижений"""
        available_achievements = []
        user_achievements = set(user.get("achievements", []))
        
        for achievement in self.achievements.values():
            if achievement.id not in user_achievements and not achievement.is_hidden:
                if not achievement.is_seasonal or self._is_season_active(achievement.season):
                    available_achievements.append(achievement)
        
        return available_achievements
    
    async def get_achievement_progress(self, user: Dict[str, Any], achievement: Achievement) -> Dict[str, Any]:
        """Получение прогресса достижения"""
        progress = {}
        
        for key, value in achievement.requirements.items():
            if key == "challenges_completed":
                current = len(user.get("completed_challenges", []))
                progress[key] = {
                    "current": current,
                    "required": value,
                    "percentage": min(100, (current / value) * 100)
                }
            elif key == "streak_days":
                current = user.get("streak", 0)
                progress[key] = {
                    "current": current,
                    "required": value,
                    "percentage": min(100, (current / value) * 100)
                }
            elif key == "referrals":
                current = len(user.get("referrals", []))
                progress[key] = {
                    "current": current,
                    "required": value,
                    "percentage": min(100, (current / value) * 100)
                }
            elif key == "social_shares":
                current = len(user.get("social_shares", []))
                progress[key] = {
                    "current": current,
                    "required": value,
                    "percentage": min(100, (current / value) * 100)
                }
            elif key == "level":
                current = user.get("level", 0)
                progress[key] = {
                    "current": current,
                    "required": value,
                    "percentage": min(100, (current / value) * 100)
                }
            elif key == "badges_collected":
                current = len(user.get("badges", []))
                progress[key] = {
                    "current": current,
                    "required": value,
                    "percentage": min(100, (current / value) * 100)
                }
        
        return progress
    
    def format_achievements_list(self, achievements: List[Achievement]) -> str:
        """Форматирование списка достижений"""
        if not achievements:
            return "У вас пока нет достижений."
        
        text = ""
        for achievement in achievements:
            text += f"{achievement.icon} {achievement.name}\n"
            text += f"📝 {achievement.description}\n"
            text += f"⭐️ +{achievement.points} очков\n\n"
        
        return text
    
    async def cleanup_expired_achievements(self):
        """Очистка истекших сезонных достижений"""
        try:
            now = datetime.now(UTC)
            
            # Находим истекшие сезонные достижения
            expired_achievements = [
                achievement for achievement in self.achievements.values()
                if achievement.is_seasonal and achievement.expires_at and achievement.expires_at < now
            ]
            
            # Удаляем истекшие достижения у пользователей
            for achievement in expired_achievements:
                await self.db.users.update_many(
                    {"achievements": achievement.id},
                    {"$pull": {"achievements": achievement.id}}
                )
            
            # Логируем очистку
            await self.db.achievement_logs.insert_one({
                "type": "cleanup",
                "timestamp": now,
                "expired_count": len(expired_achievements)
            })
            
        except Exception as e:
            logger.error(f"Ошибка при очистке истекших достижений: {e}")

# Создаем экземпляр системы достижений
achievement_system = AchievementSystem(None)  # DB будет установлен позже 