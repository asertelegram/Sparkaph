import pymongo
import logging
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mongo_test")

def main():
    # Получаем URI из .env файла
    mongodb_uri = os.getenv("MONGODB_URI")
    
    if not mongodb_uri:
        logger.error("MONGODB_URI не найден в .env файле")
        return
    
    logger.info(f"Используем URI: {mongodb_uri}")
    
    # Стратегия 1: Прямое подключение с обычным URI
    try:
        # Создаем клиента MongoDB с отключенной проверкой сертификатов
        client = pymongo.MongoClient(
            mongodb_uri,
            tlsAllowInvalidCertificates=True,    # Отключаем проверку сертификатов
            connectTimeoutMS=5000,               # Таймаут подключения
            socketTimeoutMS=5000,                # Таймаут сокета
            serverSelectionTimeoutMS=5000,       # Таймаут выбора сервера
        )
        
        # Проверяем подключение
        client.admin.command('ping')
        logger.info("✅ Подключение успешно")
        
        # Показываем доступные базы данных
        dbs = client.list_database_names()
        logger.info(f"Доступные базы данных: {dbs}")
        
        # Проверяем коллекции в базе Sparkaph
        db = client.Sparkaph
        collections = db.list_collection_names()
        logger.info(f"Коллекции в базе Sparkaph: {collections}")
        
        # Закрываем подключение
        client.close()
        return True
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    
    # Стратегия 2: Стандартное подключение (не SRV)
    try:
        logger.info("Пробуем стандартное подключение")
        standard_uri = "mongodb://Stexiel:ASER2007@ac-8nwxhnr-shard-00-00.h0r4kz4.mongodb.net:27017,ac-8nwxhnr-shard-00-01.h0r4kz4.mongodb.net:27017,ac-8nwxhnr-shard-00-02.h0r4kz4.mongodb.net:27017/Sparkaph?authSource=admin"
        
        client = pymongo.MongoClient(
            standard_uri,
            tlsAllowInvalidCertificates=True,
            connectTimeoutMS=5000, 
            socketTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
        )
        
        # Проверяем подключение
        client.admin.command('ping')
        logger.info("✅ Стандартное подключение успешно")
        
        # Закрываем подключение
        client.close()
        return True
    
    except Exception as e:
        logger.error(f"Ошибка со стандартным URI: {e}")
    
    return False

if __name__ == "__main__":
    main() 