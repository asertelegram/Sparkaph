import asyncio
import logging
from datetime import datetime, UTC, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Подключение к MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URI)
db = client.sparkaph

async def setup_test_data():
    """Создание тестовых данных для проверки функционала бота"""
    try:
        # Создаем тестовую категорию
        category = await db.categories.insert_one({
            "name": "Тестовая категория",
            "description": "Категория для тестирования",
            "created_at": datetime.now(UTC)
        })
        
        # Создаем тестового инфлюенсера
        influencer = await db.influencers.insert_one({
            "user_id": 123456789,
            "username": "test_influencer",
            "category_id": category.inserted_id,
            "created_at": datetime.now(UTC)
        })
        
        # Создаем тестовых пользователей
        users = []
        for i in range(5):
            user = await db.users.insert_one({
                "user_id": 100000000 + i,
                "username": f"test_user_{i}",
                "created_at": datetime.now(UTC),
                "last_activity": datetime.now(UTC)
            })
            users.append(user.inserted_id)
        
        # Создаем тестовые челленджи
        challenges = []
        for i in range(3):
            challenge = await db.challenges.insert_one({
                "text": f"Тестовый челлендж {i+1}",
                "description": f"Описание тестового челленджа {i+1}",
                "type": "photo",
                "category_id": category.inserted_id,
                "created_by": influencer.inserted_id,
                "created_at": datetime.now(UTC) - timedelta(days=i),
                "is_active": True
            })
            challenges.append(challenge.inserted_id)
        
        # Создаем тестовые выполнения
        for challenge_id in challenges:
            for user_id in users:
                # Создаем несколько выполнений с разным временем
                for day in range(7):
                    await db.submissions.insert_one({
                        "user_id": user_id,
                        "challenge_id": challenge_id,
                        "status": "approved",
                        "submitted_at": datetime.now(UTC) - timedelta(days=day),
                        "media_type": "photo",
                        "media_id": "test_media_id"
                    })
        
        # Создаем тестовые шаблоны
        for i in range(2):
            await db.templates.insert_one({
                "name": f"Тестовый шаблон {i+1}",
                "text": f"Текст тестового шаблона {i+1}",
                "description": f"Описание тестового шаблона {i+1}",
                "type": "photo",
                "created_by": influencer.inserted_id,
                "created_at": datetime.now(UTC),
                "usage_count": 0
            })
        
        logger.info("Тестовые данные успешно созданы")
        
    except Exception as e:
        logger.error(f"Ошибка при создании тестовых данных: {e}")
        raise

async def cleanup_test_data():
    """Удаление тестовых данных"""
    try:
        # Удаляем все тестовые данные
        await db.categories.delete_many({"name": "Тестовая категория"})
        await db.influencers.delete_many({"username": "test_influencer"})
        await db.users.delete_many({"username": {"$regex": "^test_user_"}})
        await db.challenges.delete_many({"text": {"$regex": "^Тестовый челлендж"}})
        await db.submissions.delete_many({"media_id": "test_media_id"})
        await db.templates.delete_many({"name": {"$regex": "^Тестовый шаблон"}})
        
        logger.info("Тестовые данные успешно удалены")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении тестовых данных: {e}")
        raise

async def test_statistics():
    """Тестирование функционала статистики"""
    try:
        # Получаем тестового инфлюенсера
        influencer = await db.influencers.find_one({"username": "test_influencer"})
        
        # Получаем статистику
        challenges_count = await db.challenges.count_documents({"category_id": influencer["category_id"]})
        completed_count = await db.submissions.count_documents({
            "challenge_id": {"$in": [c["_id"] async for c in db.challenges.find({"category_id": influencer["category_id"]})]},
            "status": "approved"
        })
        
        # Проверяем статистику
        assert challenges_count == 3, f"Ожидалось 3 челленджа, получено {challenges_count}"
        assert completed_count == 105, f"Ожидалось 105 выполнений, получено {completed_count}"
        
        logger.info("Тест статистики пройден успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании статистики: {e}")
        raise

async def test_templates():
    """Тестирование функционала шаблонов"""
    try:
        # Получаем тестового инфлюенсера
        influencer = await db.influencers.find_one({"username": "test_influencer"})
        
        # Получаем шаблоны
        templates = await db.templates.find({"created_by": influencer["_id"]}).to_list(length=None)
        
        # Проверяем количество шаблонов
        assert len(templates) == 2, f"Ожидалось 2 шаблона, получено {len(templates)}"
        
        # Проверяем содержимое шаблонов
        for template in templates:
            assert "name" in template, "Отсутствует поле name в шаблоне"
            assert "text" in template, "Отсутствует поле text в шаблоне"
            assert "description" in template, "Отсутствует поле description в шаблоне"
            assert "type" in template, "Отсутствует поле type в шаблоне"
            assert template["usage_count"] == 0, "Счетчик использования должен быть 0"
        
        logger.info("Тест шаблонов пройден успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании шаблонов: {e}")
        raise

async def test_challenges():
    """Тестирование функционала челленджей"""
    try:
        # Получаем тестового инфлюенсера
        influencer = await db.influencers.find_one({"username": "test_influencer"})
        
        # Получаем челленджи
        challenges = await db.challenges.find({"category_id": influencer["category_id"]}).to_list(length=None)
        
        # Проверяем количество челленджей
        assert len(challenges) == 3, f"Ожидалось 3 челленджа, получено {len(challenges)}"
        
        # Проверяем содержимое челленджей
        for challenge in challenges:
            assert "text" in challenge, "Отсутствует поле text в челлендже"
            assert "description" in challenge, "Отсутствует поле description в челлендже"
            assert "type" in challenge, "Отсутствует поле type в челлендже"
            assert challenge["is_active"] == True, "Челлендж должен быть активным"
        
        logger.info("Тест челленджей пройден успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании челленджей: {e}")
        raise

async def test_submissions():
    """Тестирование функционала выполнений"""
    try:
        # Получаем тестового инфлюенсера
        influencer = await db.influencers.find_one({"username": "test_influencer"})
        
        # Получаем все челленджи
        challenges = await db.challenges.find({"category_id": influencer["category_id"]}).to_list(length=None)
        
        # Проверяем выполнения для каждого челленджа
        for challenge in challenges:
            submissions = await db.submissions.find({
                "challenge_id": challenge["_id"],
                "status": "approved"
            }).to_list(length=None)
            
            # Проверяем количество выполнений
            assert len(submissions) == 35, f"Ожидалось 35 выполнений, получено {len(submissions)}"
            
            # Проверяем содержимое выполнений
            for submission in submissions:
                assert "user_id" in submission, "Отсутствует поле user_id в выполнении"
                assert "status" in submission, "Отсутствует поле status в выполнении"
                assert "submitted_at" in submission, "Отсутствует поле submitted_at в выполнении"
                assert "media_type" in submission, "Отсутствует поле media_type в выполнении"
        
        logger.info("Тест выполнений пройден успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании выполнений: {e}")
        raise

async def main():
    """Основная функция тестирования"""
    try:
        # Создаем тестовые данные
        await setup_test_data()
        
        # Запускаем тесты
        await test_statistics()
        await test_templates()
        await test_challenges()
        await test_submissions()
        
        # Удаляем тестовые данные
        await cleanup_test_data()
        
        logger.info("Все тесты пройдены успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 