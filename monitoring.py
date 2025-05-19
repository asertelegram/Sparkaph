import os
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()

logger = logging.getLogger(__name__)

class MonitoringSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.metrics = db.metrics
        self.alerts = db.alerts
        self.optimization_logs = db.optimization_logs
        self.metrics_interval = 300  # 5 минут
        self.alert_thresholds = {
            "cpu_percent": 80,
            "memory_percent": 80,
            "disk_percent": 90,
            "response_time": 2.0  # секунды
        }
        self.metrics_history: List[Dict] = []
        self.max_history_size = 1000
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Сбор метрик системы"""
        try:
            # Системные метрики
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Метрики MongoDB
            db_stats = await self.db.command("dbStats")
            
            metrics = {
                "timestamp": datetime.utcnow(),
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent
                },
                "database": {
                    "collections": db_stats.get("collections", 0),
                    "objects": db_stats.get("objects", 0),
                    "data_size": db_stats.get("dataSize", 0),
                    "storage_size": db_stats.get("storageSize", 0),
                    "index_size": db_stats.get("indexSize", 0)
                }
            }
            
            # Сохраняем метрики
            await self.metrics.insert_one(metrics)
            
            # Проверяем алерты
            await self.check_alerts(metrics)
            
            return metrics
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            raise
    
    async def check_alerts(self, metrics: Dict[str, Any]) -> None:
        """Проверка и создание алертов"""
        try:
            # Проверка CPU
            if metrics["system"]["cpu_percent"] > self.alert_thresholds["cpu_percent"]:
                await self.create_alert(
                    "high_cpu",
                    f"High CPU usage: {metrics['system']['cpu_percent']}%",
                    "warning"
                )
            
            # Проверка памяти
            if metrics["system"]["memory_percent"] > self.alert_thresholds["memory_percent"]:
                await self.create_alert(
                    "high_memory",
                    f"High memory usage: {metrics['system']['memory_percent']}%",
                    "warning"
                )
            
            # Проверка диска
            if metrics["system"]["disk_percent"] > self.alert_thresholds["disk_percent"]:
                await self.create_alert(
                    "low_disk_space",
                    f"Low disk space: {metrics['system']['disk_percent']}% used",
                    "critical"
                )
            
            # Проверка размера базы данных
            if metrics["database"]["data_size"] > 1_000_000_000:  # 1GB
                await self.create_alert(
                    "large_database",
                    f"Large database size: {metrics['database']['data_size']} bytes",
                    "warning"
                )
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            raise
    
    async def create_alert(self, alert_type: str, message: str, severity: str) -> None:
        """Создание алерта"""
        try:
            alert = {
                "type": alert_type,
                "message": message,
                "severity": severity,
                "created_at": datetime.utcnow(),
                "status": "active"
            }
            await self.alerts.insert_one(alert)
            
            # Отправляем уведомление
            await self.send_alert_notification(alert)
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            raise
    
    async def send_alert_notification(self, alert: Dict[str, Any]) -> None:
        """Отправка уведомления об алерте"""
        try:
            # TODO: Реализовать отправку уведомлений (Telegram, Email и т.д.)
            logger.warning(f"Alert: {alert['message']} (Severity: {alert['severity']})")
        except Exception as e:
            logger.error(f"Error sending alert notification: {e}")
            raise
    
    async def optimize_database(self) -> Dict[str, Any]:
        """Оптимизация базы данных"""
        try:
            # Анализ индексов
            index_stats = await self.db.command("collStats", "challenges")
            
            # Оптимизация индексов
            await self.db.command("reIndex")
            
            # Очистка старых данных
            old_date = datetime.utcnow() - timedelta(days=30)
            await self.metrics.delete_many({"timestamp": {"$lt": old_date}})
            
            # Логируем оптимизацию
            optimization_log = {
                "timestamp": datetime.utcnow(),
                "index_stats": index_stats,
                "actions": ["reindex", "cleanup_old_metrics"]
            }
            await self.optimization_logs.insert_one(optimization_log)
            
            return optimization_log
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            raise
    
    async def get_system_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Получение статистики системы"""
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Получаем метрики за последние hours часов
            metrics = await self.metrics.find({
                "timestamp": {"$gte": start_time}
            }).sort("timestamp", 1).to_list(length=None)
            
            # Получаем активные алерты
            active_alerts = await self.alerts.find({
                "status": "active"
            }).to_list(length=None)
            
            # Получаем последнюю оптимизацию
            last_optimization = await self.optimization_logs.find_one(
                sort=[("timestamp", -1)]
            )
            
            return {
                "metrics": metrics,
                "active_alerts": active_alerts,
                "last_optimization": last_optimization
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            raise
    
    async def start_monitoring(self, interval: int = 300) -> None:
        """Запуск мониторинга"""
        try:
            while True:
                await self.collect_metrics()
                await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            raise

# Создаем глобальный экземпляр системы мониторинга
monitoring_system = None

def init_monitoring(db: AsyncIOMotorDatabase) -> None:
    """Инициализация системы мониторинга"""
    global monitoring_system
    monitoring_system = MonitoringSystem(db)

class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.requests_count = 0
        self.total_response_time = 0
    
    async def measure_response_time(self, func):
        """Измерение времени ответа функции"""
        start = time.time()
        try:
            result = await func
            response_time = time.time() - start
            
            self.requests_count += 1
            self.total_response_time += response_time
            
            # Логируем медленные запросы
            if response_time > self.alert_thresholds["response_time"]:
                logger.warning(f"Slow request detected: {func.__name__} took {response_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    
    def get_statistics(self) -> Dict:
        """Получение статистики производительности"""
        uptime = time.time() - self.start_time
        avg_response_time = self.total_response_time / self.requests_count if self.requests_count > 0 else 0
        
        return {
            "uptime": round(uptime, 2),
            "requests_count": self.requests_count,
            "average_response_time": round(avg_response_time, 3),
            "requests_per_second": round(self.requests_count / uptime, 2) if uptime > 0 else 0
        }

# Создаем экземпляры мониторов
system_monitor = None
performance_monitor = PerformanceMonitor()

async def init_monitoring(db: AsyncIOMotorClient):
    """Инициализация системы мониторинга"""
    global system_monitor
    system_monitor = MonitoringSystem(db.metrics)
    
    # Запускаем сбор метрик в фоновом режиме
    asyncio.create_task(collect_metrics_periodically())

async def collect_metrics_periodically():
    """Периодический сбор метрик"""
    while True:
        try:
            await monitoring_system.collect_metrics()
            await asyncio.sleep(monitoring_system.metrics_interval)
        except Exception as e:
            logger.error(f"Error in metrics collection: {e}")
            await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой

def get_performance_monitor() -> PerformanceMonitor:
    """Получение экземпляра монитора производительности"""
    return performance_monitor 