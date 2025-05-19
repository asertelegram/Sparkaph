import logging
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RoleSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create_role(self, name: str, permissions: List[str]) -> bool:
        try:
            await self.db.roles.insert_one({"name": name, "permissions": permissions})
            return True
        except Exception as e:
            logger.error(f"Ошибка при создании роли: {e}")
            return False

    async def assign_role(self, user_id: int, role_name: str) -> bool:
        try:
            await self.db.users.update_one({"user_id": user_id}, {"$set": {"role": role_name}})
            return True
        except Exception as e:
            logger.error(f"Ошибка при назначении роли: {e}")
            return False

    async def get_user_role(self, user_id: int) -> Optional[str]:
        user = await self.db.users.find_one({"user_id": user_id})
        return user.get("role") if user else None

    async def has_permission(self, user_id: int, permission: str) -> bool:
        user = await self.db.users.find_one({"user_id": user_id})
        if not user or "role" not in user:
            return False
        role = await self.db.roles.find_one({"name": user["role"]})
        return permission in (role.get("permissions") or [])

    async def get_roles(self) -> List[Dict[str, Any]]:
        return await self.db.roles.find().to_list(length=None)

    async def get_permissions(self, role_name: str) -> List[str]:
        role = await self.db.roles.find_one({"name": role_name})
        return role.get("permissions") if role else [] 