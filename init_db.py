import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получение URI из переменных окружения
MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv('MONGODB_DB_NAME', 'Sparkaph')

async def init_database():
    try:
        # Подключение к MongoDB
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        
        # Создание коллекций и индексов
        collections = {
            'users': [
                ('user_id', 1),  # Уникальный индекс для user_id
                ('username', 1),  # Индекс для поиска по username
                ('points', -1),  # Индекс для сортировки по очкам
            ],
            'categories': [
                ('name', 1),  # Уникальный индекс для названия категории
            ],
            'challenges': [
                ('category_id', 1),  # Индекс для поиска по категории
                ('status', 1),  # Индекс для фильтрации по статусу
                ('created_at', -1),  # Индекс для сортировки по дате создания
            ],
            'submissions': [
                ('user_id', 1),  # Индекс для поиска по пользователю
                ('challenge_id', 1),  # Индекс для поиска по челленджу
                ('status', 1),  # Индекс для фильтрации по статусу
                ('submitted_at', -1),  # Индекс для сортировки по дате отправки
            ],
            'influencers': [
                ('user_id', 1),  # Уникальный индекс для user_id
                ('username', 1),  # Индекс для поиска по username
                ('followers_count', -1),  # Индекс для сортировки по количеству подписчиков
            ],
            'metrics': [
                ('timestamp', -1),  # Индекс для сортировки по времени
                ('type', 1),  # Индекс для фильтрации по типу метрики
            ],
            'alerts': [
                ('timestamp', -1),  # Индекс для сортировки по времени
                ('status', 1),  # Индекс для фильтрации по статусу
            ]
        }
        
        # Создание коллекций и индексов
        for collection_name, indexes in collections.items():
            # Создание коллекции
            await db.create_collection(collection_name)
            logger.info(f"Создана коллекция: {collection_name}")
            
            # Создание индексов
            for index in indexes:
                if len(index) == 2:
                    field, direction = index
                    await db[collection_name].create_index([(field, direction)])
                    logger.info(f"Создан индекс {field} ({direction}) для коллекции {collection_name}")
                elif len(index) == 3:
                    field, direction, unique = index
                    await db[collection_name].create_index([(field, direction)], unique=unique)
                    logger.info(f"Создан уникальный индекс {field} ({direction}) для коллекции {collection_name}")
        
        # Создание валидаторов для коллекций
        validators = {
            'users': {
                'validator': {
                    '$jsonSchema': {
                        'bsonType': 'object',
                        'required': ['user_id', 'username', 'points', 'joined_at'],
                        'properties': {
                            'user_id': {'bsonType': 'int'},
                            'username': {'bsonType': 'string'},
                            'points': {'bsonType': 'int'},
                            'current_challenge': {'bsonType': ['objectId', 'null']},
                            'completed_challenges': {'bsonType': 'array'},
                            'subscription': {'bsonType': 'bool'},
                            'joined_at': {'bsonType': 'date'},
                            'last_activity': {'bsonType': 'date'},
                            'challenge_started_at': {'bsonType': ['date', 'null']},
                            'gender': {'bsonType': ['string', 'null']},
                            'age': {'bsonType': ['string', 'null']}
                        }
                    }
                }
            },
            'challenges': {
                'validator': {
                    '$jsonSchema': {
                        'bsonType': 'object',
                        'required': ['category_id', 'text', 'max_users', 'status', 'created_at'],
                        'properties': {
                            'category_id': {'bsonType': 'objectId'},
                            'text': {'bsonType': 'string'},
                            'description': {'bsonType': ['string', 'null']},
                            'max_users': {'bsonType': 'int'},
                            'taken_by': {'bsonType': 'array'},
                            'status': {'bsonType': 'string'},
                            'created_at': {'bsonType': 'date'}
                        }
                    }
                }
            }
        }
        
        # Применение валидаторов
        for collection_name, validator in validators.items():
            await db.command({
                'collMod': collection_name,
                'validator': validator['validator']
            })
            logger.info(f"Применен валидатор для коллекции {collection_name}")
        
        logger.info("База данных успешно инициализирована!")
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(init_database()) 