import os
import asyncio
from datetime import datetime, UTC
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Инициализация клиента MongoDB
mongo_client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = mongo_client.Sparkaph

# Начальные категории
categories = [
    {
        "name": "Интервью",
        "description": "Вопросы для самопознания и сторителлинга"
    },
    {
        "name": "Саморазвитие",
        "description": "Задания для личностного роста"
    },
    {
        "name": "Хардкор",
        "description": "Экстремальные действия и испытания"
    },
    {
        "name": "С друзьями",
        "description": "Челленджи для выполнения с друзьями"
    },
    {
        "name": "Для влюбленных",
        "description": "Романтические задания для пар"
    },
    {
        "name": "Бонус",
        "description": "Специальные задания с повышенными наградами"
    }
]

# Начальные челленджи
challenges = [
    # Интервью
    {
        "category": "Интервью",
        "text": "Что бы ты сделал, если завтра был бы последний день твоей жизни?",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Интервью",
        "text": "Какой момент ты бы хотел прожить ещё раз?",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Интервью",
        "text": "За что тебе реально стыдно до сих пор?",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Интервью",
        "text": "Какое твое самое большое достижение?",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Интервью",
        "text": "Что бы ты изменил в своем прошлом?",
        "max_users": 5,
        "status": "active"
    },
    
    # Саморазвитие
    {
        "category": "Саморазвитие",
        "text": "Прочитай книгу, которую давно откладывал",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Саморазвитие",
        "text": "Выучи 10 новых слов на иностранном языке",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Саморазвитие",
        "text": "Сделай утреннюю зарядку",
        "max_users": 5,
        "status": "active"
    },
    
    # Хардкор
    {
        "category": "Хардкор",
        "text": "Пробеги 5 километров",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Хардкор",
        "text": "Сделай 100 отжиманий",
        "max_users": 5,
        "status": "active"
    },
    
    # С друзьями
    {
        "category": "С друзьями",
        "text": "Сыграй в настольную игру с друзьями",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "С друзьями",
        "text": "Сделай совместное фото с другом",
        "max_users": 5,
        "status": "active"
    },
    
    # Для влюбленных
    {
        "category": "Для влюбленных",
        "text": "Сделай сюрприз своей второй половинке",
        "max_users": 5,
        "status": "active"
    },
    {
        "category": "Для влюбленных",
        "text": "Напиши стихотворение о любви",
        "max_users": 5,
        "status": "active"
    },
    
    # Бонус
    {
        "category": "Бонус",
        "text": "Выполни любое задание из другой категории и получи двойные очки",
        "max_users": 5,
        "status": "active"
    }
]

async def init_db():
    # Очистка существующих данных
    await db.categories.delete_many({})
    await db.challenges.delete_many({})
    
    # Добавление категорий
    for category in categories:
        await db.categories.insert_one({
            "name": category["name"],
            "description": category["description"],
            "created_at": datetime.now(UTC)
        })
    
    # Получение ID категорий
    category_map = {}
    async for category in db.categories.find():
        category_map[category["name"]] = category["_id"]
    
    # Добавление челленджей
    for challenge in challenges:
        await db.challenges.insert_one({
            "category_id": category_map[challenge["category"]],
            "text": challenge["text"],
            "max_users": challenge["max_users"],
            "taken_by": [],
            "status": challenge["status"],
            "created_at": datetime.now(UTC)
        })
    
    print("База данных успешно инициализирована!")

if __name__ == "__main__":
    asyncio.run(init_db()) 