import logging
import random
from datetime import datetime, UTC, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from aiogram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwoFASystem:
    def __init__(self, db: AsyncIOMotorDatabase, bot: Bot):
        self.db = db
        self.bot = bot

    async def generate_code(self, user_id: int) -> str:
        code = str(random.randint(100000, 999999))
        expires_at = datetime.now(UTC) + timedelta(minutes=5)
        await self.db.twofa.insert_one({
            "user_id": user_id,
            "code": code,
            "expires_at": expires_at,
            "used": False
        })
        return code

    async def send_code(self, user_id: int, code: str, method: str = "telegram", email: Optional[str] = None) -> bool:
        try:
            if method == "telegram":
                await self.bot.send_message(user_id, f"Ваш код подтверждения: {code}")
                return True
            elif method == "email" and email:
                # Здесь должна быть интеграция с email-сервисом
                logger.info(f"Отправка кода {code} на email {email}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при отправке 2FA кода: {e}")
            return False

    async def verify_code(self, user_id: int, code: str) -> bool:
        record = await self.db.twofa.find_one({"user_id": user_id, "code": code, "used": False})
        if not record:
            return False
        if record["expires_at"] < datetime.now(UTC):
            return False
        await self.db.twofa.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
        await self.db.users.update_one({"user_id": user_id}, {"$set": {"twofa_verified": True}})
        return True

    async def is_verified(self, user_id: int) -> bool:
        user = await self.db.users.find_one({"user_id": user_id})
        return bool(user and user.get("twofa_verified")) 