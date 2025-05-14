# Sparkaph

Telegram-бот, мотивирующий пользователей ежедневно выполнять челленджи в разных категориях (интервью, саморазвитие, хардкор, с друзьями и др.), получать очки и продвигаться в топе.

## Функциональность

### Пользовательский бот
- Регистрация и выбор челленджей по категориям
- Отправка фото/видео/текста с результатами выполнения
- Напоминания о выполнении через 6 и 10 часов
- Рейтинговая система с очками
- Статистика личных достижений
- Автоматическая проверка подписки на канал

### Админский бот
- Проверка и подтверждение/отклонение челленджей
- Управление категориями и челленджами
- Подробная статистика для инвесторов:
  - DAU/WAU/MAU метрики
  - Retention за день/неделю/3 недели
  - Демографическая статистика
  - Статистика по категориям и выполнениям

## Технический стек
- Python 3.10+
- aiogram 3.x (Telegram Bot API)
- MongoDB (для хранения данных)
- Бесплатный хостинг (Render/Railway/Cyclic)

## Установка и запуск

### Локальный запуск

1. Клонировать репозиторий:
```bash
git clone https://github.com/yourusername/sparkaph.git
cd sparkaph
```

2. Установить зависимости:
```bash
pip install -r requirements.txt
```

3. Создать файл `.env` в корневой директории со следующими переменными:
```bash
USER_BOT_TOKEN=<токен пользовательского бота>
ADMIN_BOT_TOKEN=<токен админского бота>
MONGODB_URI=<строка подключения MongoDB>
CHANNEL_ID=<ID канала, например @SparkaphChannel>
ADMIN_ID=<ID администратора>
```

4. Инициализировать базу данных:
```bash
python init_db.py
```

5. Запустить боты:

   Пользовательский бот:
   ```bash
   python user_bot.py
   ```

   Админский бот (в отдельном терминале):
   ```bash
   python admin_bot.py
   ```

### Деплой на Render

1. Создайте аккаунт на [Render](https://render.com/)

2. Подключите свой GitHub репозиторий

3. Создайте новый сервис типа "Web Service"

4. Укажите настройки согласно `render.yaml`

5. Настройте переменные окружения в интерфейсе Render:
   - USER_BOT_TOKEN
   - ADMIN_BOT_TOKEN
   - MONGODB_URI
   - CHANNEL_ID
   - ADMIN_ID

6. Запустите деплой

## База данных MongoDB

### Структура коллекций

#### users
- `user_id`: ID пользователя Telegram
- `username`: Имя пользователя
- `points`: Очки пользователя
- `current_challenge`: ID текущего челленджа
- `completed_challenges`: Массив ID выполненных челленджей
- `subscription`: Статус подписки на канал
- `joined_at`: Дата регистрации
- `last_activity`: Дата последней активности
- `challenge_started_at`: Время начала текущего челленджа
- `gender`: Пол пользователя
- `age`: Возрастная группа

#### categories
- `name`: Название категории
- `description`: Описание категории
- `created_at`: Дата создания

#### challenges
- `category_id`: ID категории
- `text`: Текст челленджа
- `description`: Описание (опционально)
- `max_users`: Максимальное количество пользователей
- `taken_by`: Массив ID пользователей, взявших челлендж
- `status`: Статус челленджа (active/disabled)
- `created_at`: Дата создания

#### submissions
- `user_id`: ID пользователя
- `challenge_id`: ID челленджа
- `text`: Текстовый ответ
- `media`: ID медиа (фото/видео)
- `media_type`: Тип медиа
- `submitted_at`: Время отправки
- `reviewed_at`: Время проверки
- `status`: Статус (pending/approved/rejected)
- `reject_reason`: Причина отказа (если отклонено)

## Контактная информация

По всем вопросам обращайтесь: @AserAbiken # Sparkaph
git
init
git
add
README.md
git
commit
-m
первый коммит
git
branch
-M
main
git
remote
add
origin
https://github.com/asertelegram/Sparkaph.git
git
push
-u
origin
main
