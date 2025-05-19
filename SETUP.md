# Настройка проекта Sparkaph

## Требования
- Python 3.8+
- MongoDB
- Telegram Bot Token
- API ключи для социальных сетей (TikTok, Instagram)

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/sparkaph.git
cd sparkaph
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
pip install -r requirements.txt
```

3. Создайте файл `.env` в корневой директории проекта и добавьте следующие переменные:
```env
# Telegram Bot Token
BOT_TOKEN=your_bot_token_here

# MongoDB Connection
MONGODB_URI=mongodb://localhost:27017
DB_NAME=sparkaph

# Social Media API Keys
TIKTOK_API_KEY=your_tiktok_api_key_here
INSTAGRAM_API_KEY=your_instagram_api_key_here

# Admin Settings
ADMIN_USER_ID=your_admin_telegram_id_here
```

## Получение API ключей

### TikTok API
1. Зарегистрируйтесь как разработчик на [TikTok for Developers](https://developers.tiktok.com/)
2. Создайте новое приложение
3. Получите API ключ в разделе "App Management"

### Instagram API
1. Создайте аккаунт разработчика на [Meta for Developers](https://developers.facebook.com/)
2. Создайте новое приложение
3. Добавьте продукт "Instagram Graph API"
4. Получите API ключ в настройках приложения

## Запуск

1. Убедитесь, что MongoDB запущена
2. Запустите бота:
```bash
python user_bot.py
```

## Тестирование

Запустите тесты:
```bash
pytest tests/
```

## Структура проекта

```
sparkaph/
├── user_bot.py           # Основной файл бота
├── admin_bot.py          # Админ-панель
├── social_media.py       # Модуль для работы с соцсетями
├── achievements.py       # Система достижений
├── requirements.txt      # Зависимости проекта
├── tests/               # Тесты
│   ├── test_achievements.py
│   └── test_social_media.py
└── .env                 # Конфигурация (не включен в репозиторий)
```

## Функциональность

### Основные возможности
- Регистрация и авторизация пользователей
- Система челленджей
- Система достижений
- Интеграция с социальными сетями
- Админ-панель для управления

### Социальные сети
- Публикация в TikTok
- Публикация в Instagram (посты и сторис)
- Отслеживание статистики публикаций

## Безопасность

- Все API ключи хранятся в файле `.env`
- Файл `.env` добавлен в `.gitignore`
- Используется безопасное хранение паролей
- Реализована система модерации контента

## Поддержка

При возникновении проблем:
1. Проверьте логи в консоли
2. Убедитесь, что все переменные окружения установлены
3. Проверьте подключение к MongoDB
4. Проверьте валидность API ключей

## Лицензия

MIT License 