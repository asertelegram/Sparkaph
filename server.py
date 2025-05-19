import os
import logging
from typing import Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from challenges import ChallengeManager
from rating import RatingSystem
from monitoring import MonitoringSystem, PerformanceMonitor
from admin_panel import AdminPanel

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Server:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("DB_NAME", "sparkaph")
        self.client = None
        self.db = None
        
        # Компоненты системы
        self.challenge_manager = None
        self.rating_system = None
        self.monitoring_system = None
        self.admin_panel = None
        self.performance_monitor = PerformanceMonitor()

    async def connect(self) -> None:
        """Подключение к базе данных"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            
            # Инициализация компонентов
            self.challenge_manager = ChallengeManager(self.db)
            self.rating_system = RatingSystem(self.db)
            self.monitoring_system = MonitoringSystem(self.db)
            self.admin_panel = AdminPanel(self.db)
            
            # Запуск мониторинга
            await self.monitoring_system.start_monitoring()
            
            logger.info("Successfully connected to database")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    async def disconnect(self) -> None:
        """Отключение от базы данных"""
        try:
            if self.client:
                self.client.close()
                logger.info("Successfully disconnected from database")
        except Exception as e:
            logger.error(f"Error disconnecting from database: {e}")
            raise

    async def get_system_status(self) -> Dict[str, Any]:
        """Получение статуса системы"""
        try:
            return {
                "status": "running",
                "database": {
                    "connected": bool(self.client),
                    "name": self.db_name
                },
                "components": {
                    "challenge_manager": bool(self.challenge_manager),
                    "rating_system": bool(self.rating_system),
                    "monitoring_system": bool(self.monitoring_system),
                    "admin_panel": bool(self.admin_panel)
                },
                "performance": self.performance_monitor.get_statistics(),
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            raise

# Создаем глобальный экземпляр сервера
server = Server()

async def init_server() -> Server:
    """Инициализация сервера"""
    await server.connect()
    return server

async def shutdown_server() -> None:
    """Завершение работы сервера"""
    await server.disconnect() 