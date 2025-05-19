import os
import csv
import json
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from models import Challenge
from datetime import datetime

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

mongo_client = AsyncIOMotorClient(MONGODB_URI)
db = mongo_client["Sparkaph"]
challenges_collection = db["challenges"]

async def load_challenges_from_csv(csv_path: str, category_id: str, author_id: int = None):
    """
    Загружает челленджи из CSV-файла в коллекцию challenges.
    Формат CSV: title,description,points,media_url
    """
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            challenge = Challenge(
                challenge_id=str(os.urandom(8).hex()),
                category_id=category_id,
                author_id=author_id,
                title=row["title"],
                description=row.get("description", ""),
                points=int(row.get("points", 10)),
                is_active=True,
                created_at=datetime.utcnow(),
                media_url=row.get("media_url")
            )
            await challenges_collection.insert_one(challenge.dict())
    print("Челленджи успешно загружены из CSV!")

async def load_challenges_from_json(json_path: str, category_id: str, author_id: int = None):
    """
    Загружает челленджи из JSON-файла в коллекцию challenges.
    Формат JSON: список объектов с полями title, description, points, media_url
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
        for row in data:
            challenge = Challenge(
                challenge_id=str(os.urandom(8).hex()),
                category_id=category_id,
                author_id=author_id,
                title=row["title"],
                description=row.get("description", ""),
                points=int(row.get("points", 10)),
                is_active=True,
                created_at=datetime.utcnow(),
                media_url=row.get("media_url")
            )
            await challenges_collection.insert_one(challenge.dict())
    print("Челленджи успешно загружены из JSON!")

# Пример использования:
# import asyncio
# asyncio.run(load_challenges_from_csv("challenges.csv", category_id="selfdev"))
# asyncio.run(load_challenges_from_json("challenges.json", category_id="selfdev"))

# Пример структуры CSV:
# title,description,points,media_url
# "Сделай зарядку","Начни утро с зарядки",10,
# "Прочитай статью","Выбери интересную статью и прочитай",15,

# Пример структуры JSON:
# [
#   {"title": "Сделай зарядку", "description": "Начни утро с зарядки", "points": 10},
#   {"title": "Прочитай статью", "description": "Выбери интересную статью и прочитай", "points": 15}
# ] 