import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self._is_connected = False
    
    async def connect(self):
        """Подключение к базе данных"""
        try:
            load_dotenv()
            mongodb_uri = os.getenv("MONGODB_URI")
            
            if not mongodb_uri:
                raise ValueError("MONGODB_URI не найден в .env файле")
            
            # Добавляем параметры для обхода проблем с SSL
            if "?" in mongodb_uri:
                if "tlsAllowInvalidCertificates=true" not in mongodb_uri:
                    mongodb_uri += "&tlsAllowInvalidCertificates=true"
            else:
                mongodb_uri += "?tlsAllowInvalidCertificates=true"
            
            self.client = AsyncIOMotorClient(
                mongodb_uri,
                tlsAllowInvalidCertificates=True,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                serverSelectionTimeoutMS=10000,
                heartbeatFrequencyMS=15000,
                retryWrites=False,
            )
            
            # Проверяем подключение
            await self.client.admin.command('ping')
            
            self.db = self.client.Sparkaph
            self._is_connected = True
            logger.info("Успешное подключение к MongoDB")
            
            # Создаем индексы
            await self.create_indexes()
            
        except Exception as e:
            logger.error(f"Ошибка подключения к MongoDB: {e}")
            raise
    
    async def create_indexes(self):
        """Создание необходимых индексов"""
        try:
            # Индексы для users
            await self.db.users.create_index("user_id", unique=True)
            await self.db.users.create_index("username")
            await self.db.users.create_index("points")
            await self.db.users.create_index("last_activity")
            await self.db.users.create_index("last_fortune_spin")
            
            # Индексы для submissions
            await self.db.submissions.create_index("user_id")
            await self.db.submissions.create_index("challenge_id")
            await self.db.submissions.create_index("status")
            await self.db.submissions.create_index("submitted_at")
            await self.db.submissions.create_index("media_type")
            
            # Индексы для challenges
            await self.db.challenges.create_index("category_id")
            await self.db.challenges.create_index("status")
            await self.db.challenges.create_index("taken_by")
            
            # Индексы для categories
            await self.db.categories.create_index("name", unique=True)
            
            logger.info("Индексы успешно созданы")
        except Exception as e:
            logger.error(f"Ошибка при создании индексов: {e}")
            raise
    
    async def close(self):
        """Закрытие подключения к базе данных"""
        if self.client:
            self.client.close()
            self._is_connected = False
            logger.info("Подключение к MongoDB закрыто")
    
    @property
    def is_connected(self):
        """Проверка статуса подключения"""
        return self._is_connected

# Создаем глобальный экземпляр менеджера базы данных
db_manager = DatabaseManager() 