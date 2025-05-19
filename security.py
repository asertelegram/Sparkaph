import logging
import time
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
import hashlib
import secrets
import re
from aiogram import Bot
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecuritySystem:
    def __init__(self, bot: Bot, db: AsyncIOMotorDatabase):
        self.bot = bot
        self.db = db
        
        # Настройки rate limiting
        self.rate_limits = {
            "message": {"limit": 20, "window": 60},  # 20 сообщений в минуту
            "callback": {"limit": 30, "window": 60},  # 30 callback-запросов в минуту
            "challenge": {"limit": 5, "window": 300},  # 5 челленджей в 5 минут
            "media": {"limit": 10, "window": 300}  # 10 медиафайлов в 5 минут
        }
        
        # Настройки спам-фильтра
        self.spam_patterns = [
            r"(?i)(buy|sell|earn|money|profit|investment|bitcoin|crypto)",
            r"(?i)(casino|bet|gambling|lottery)",
            r"(?i)(porn|sex|adult)",
            r"(?i)(drugs|pharmacy|medication)",
            r"(?i)(hack|crack|cheat|exploit)",
            r"(?i)(scam|fraud|fake)",
            r"(?i)(click here|register now|sign up|subscribe)",
            r"(?i)(free|discount|offer|deal|sale)",
            r"(?i)(winner|prize|reward|bonus)",
            r"(?i)(urgent|important|emergency|alert)"
        ]
        
        # Компилируем регулярные выражения
        self.spam_regex = [re.compile(pattern) for pattern in self.spam_patterns]
    
    async def check_rate_limit(
        self,
        user_id: int,
        action_type: str
    ) -> Tuple[bool, Optional[int]]:
        """Проверка rate limit для пользователя"""
        try:
            # Получаем настройки для типа действия
            limit_config = self.rate_limits.get(action_type)
            if not limit_config:
                return True, None
            
            # Получаем текущее время
            now = datetime.now(UTC)
            window_start = now - timedelta(seconds=limit_config["window"])
            
            # Подсчитываем количество действий в окне
            count = await self.db.rate_limits.count_documents({
                "user_id": user_id,
                "action_type": action_type,
                "timestamp": {"$gte": window_start}
            })
            
            # Проверяем, не превышен ли лимит
            if count >= limit_config["limit"]:
                # Вычисляем время до сброса лимита
                oldest_action = await self.db.rate_limits.find_one(
                    {
                        "user_id": user_id,
                        "action_type": action_type,
                        "timestamp": {"$gte": window_start}
                    },
                    sort=[("timestamp", 1)]
                )
                
                if oldest_action:
                    reset_time = oldest_action["timestamp"] + timedelta(seconds=limit_config["window"])
                    wait_seconds = int((reset_time - now).total_seconds())
                    return False, wait_seconds
            
            # Записываем новое действие
            await self.db.rate_limits.insert_one({
                "user_id": user_id,
                "action_type": action_type,
                "timestamp": now
            })
            
            return True, None
            
        except Exception as e:
            logger.error(f"Ошибка при проверке rate limit: {e}")
            return False, None
    
    async def check_spam(self, text: str) -> Tuple[bool, Optional[str]]:
        """Проверка текста на спам"""
        try:
            # Проверяем текст на соответствие спам-паттернам
            for pattern in self.spam_regex:
                if pattern.search(text):
                    return False, f"Обнаружен спам-паттерн: {pattern.pattern}"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Ошибка при проверке спама: {e}")
            return False, None
    
    async def generate_auth_token(self, user_id: int) -> str:
        """Генерация токена аутентификации"""
        try:
            # Генерируем случайный токен
            token = secrets.token_urlsafe(32)
            
            # Сохраняем токен в базе данных
            await self.db.auth_tokens.insert_one({
                "user_id": user_id,
                "token": token,
                "created_at": datetime.now(UTC),
                "expires_at": datetime.now(UTC) + timedelta(days=7),
                "is_active": True
            })
            
            return token
            
        except Exception as e:
            logger.error(f"Ошибка при генерации токена: {e}")
            return None
    
    async def validate_auth_token(self, token: str) -> Tuple[bool, Optional[int]]:
        """Проверка токена аутентификации"""
        try:
            # Ищем токен в базе данных
            auth_token = await self.db.auth_tokens.find_one({
                "token": token,
                "is_active": True,
                "expires_at": {"$gt": datetime.now(UTC)}
            })
            
            if not auth_token:
                return False, None
            
            return True, auth_token["user_id"]
            
        except Exception as e:
            logger.error(f"Ошибка при проверке токена: {e}")
            return False, None
    
    async def revoke_auth_token(self, token: str) -> bool:
        """Отзыв токена аутентификации"""
        try:
            result = await self.db.auth_tokens.update_one(
                {"token": token},
                {"$set": {"is_active": False}}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка при отзыве токена: {e}")
            return False
    
    async def get_user_security_logs(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получение логов безопасности пользователя"""
        try:
            logs = await self.db.security_logs.find({
                "user_id": user_id
            }).sort("timestamp", -1).limit(limit).to_list(length=None)
            
            return logs
            
        except Exception as e:
            logger.error(f"Ошибка при получении логов безопасности: {e}")
            return []
    
    async def log_security_event(
        self,
        user_id: int,
        event_type: str,
        details: Dict[str, Any]
    ) -> bool:
        """Логирование события безопасности"""
        try:
            await self.db.security_logs.insert_one({
                "user_id": user_id,
                "event_type": event_type,
                "details": details,
                "timestamp": datetime.now(UTC),
                "ip_address": details.get("ip_address"),
                "user_agent": details.get("user_agent")
            })
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при логировании события безопасности: {e}")
            return False
    
    async def get_security_stats(self) -> Dict[str, Any]:
        """Получение статистики безопасности"""
        try:
            now = datetime.now(UTC)
            day_ago = now - timedelta(days=1)
            
            # Общая статистика
            total_events = await self.db.security_logs.count_documents({})
            events_24h = await self.db.security_logs.count_documents({
                "timestamp": {"$gte": day_ago}
            })
            
            # Статистика по типам событий
            event_types = await self.db.security_logs.distinct("event_type")
            event_stats = {}
            
            for event_type in event_types:
                count = await self.db.security_logs.count_documents({
                    "event_type": event_type
                })
                event_stats[event_type] = count
            
            # Статистика по rate limits
            rate_limit_stats = {}
            for action_type in self.rate_limits:
                count = await self.db.rate_limits.count_documents({
                    "action_type": action_type,
                    "timestamp": {"$gte": day_ago}
                })
                rate_limit_stats[action_type] = count
            
            return {
                "total_events": total_events,
                "events_24h": events_24h,
                "by_event_type": event_stats,
                "rate_limits_24h": rate_limit_stats
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики безопасности: {e}")
            return {}
    
    async def cleanup_old_data(self) -> Dict[str, int]:
        """Очистка старых данных"""
        try:
            now = datetime.now(UTC)
            
            # Удаляем старые rate limits
            rate_limit_result = await self.db.rate_limits.delete_many({
                "timestamp": {"$lt": now - timedelta(days=1)}
            })
            
            # Деактивируем старые токены
            token_result = await self.db.auth_tokens.update_many(
                {
                    "expires_at": {"$lt": now}
                },
                {"$set": {"is_active": False}}
            )
            
            # Удаляем старые логи
            log_result = await self.db.security_logs.delete_many({
                "timestamp": {"$lt": now - timedelta(days=30)}
            })
            
            return {
                "rate_limits_deleted": rate_limit_result.deleted_count,
                "tokens_deactivated": token_result.modified_count,
                "logs_deleted": log_result.deleted_count
            }
            
        except Exception as e:
            logger.error(f"Ошибка при очистке старых данных: {e}")
            return {} 