import pymongo
import ssl
import logging
import sys
import dns.resolver  # необходимо для SRV подключения

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mongo_test")

# Ваши данные подключения
CONNECTION_STRING = "mongodb+srv://ЗАМЕНИТЬ_ЛОГИН:ЗАМЕНИТЬ_ПАРОЛЬ@ac-8nwxhnr-shard-00-00.h0r4kz4.mongodb.net"

# Функция для тестирования подключения с разными настройками
def test_connection(title, uri, **kwargs):
    logger.info(f"Тест {title}: Подключаемся с URI: {uri}")
    try:
        client = pymongo.MongoClient(uri, **kwargs)
        # Проверка подключения выполнением простой команды
        client.admin.command('ping')
        logger.info(f"✅ Тест {title}: Успешное подключение")
        return True
    except pymongo.errors.ConfigurationError as e:
        logger.error(f"❌ Тест {title}: Ошибка конфигурации: {e}")
    except pymongo.errors.ConnectionFailure as e:
        logger.error(f"❌ Тест {title}: Ошибка подключения: {e}")
    except pymongo.errors.ServerSelectionTimeoutError as e:
        logger.error(f"❌ Тест {title}: Ошибка выбора сервера: {e}")
    except Exception as e:
        logger.error(f"❌ Тест {title}: Непредвиденная ошибка: {e}")
    return False

def main():
    if "ЗАМЕНИТЬ" in CONNECTION_STRING:
        print("⚠️ Пожалуйста, замените данные подключения в скрипте!")
        return
    
    # Тест 1: Стандартное подключение
    test_connection(
        "Стандартное",
        CONNECTION_STRING,
        connectTimeoutMS=5000, 
        socketTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
    )
    
    # Тест 2: Без проверки сертификатов
    test_connection(
        "Без проверки SSL", 
        CONNECTION_STRING, 
        ssl=True,
        tlsAllowInvalidCertificates=True,
        connectTimeoutMS=5000, 
        socketTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
    )
    
    # Тест 3: С альтернативным TLS
    test_connection(
        "Альтернативный TLS",
        CONNECTION_STRING, 
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE,
        connectTimeoutMS=5000, 
        socketTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
    )
    
    # Тест 4: С альтернативным SSL-контекстом
    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        test_connection(
            "С SSL-контекстом",
            CONNECTION_STRING, 
            tls=True,
            tlsInsecure=True,
            ssl_cert_reqs=ssl.CERT_NONE,
            connectTimeoutMS=5000, 
            socketTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
        )
    except Exception as e:
        logger.error(f"Не удалось создать SSL-контекст: {e}")

if __name__ == "__main__":
    main() 