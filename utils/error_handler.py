import logging
import traceback
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from database.operations import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

class ErrorHandler:
    def __init__(self):
        self.db = Database()

    async def log_error(self, error: Exception, context: ContextTypes.DEFAULT_TYPE):
        """Логирует ошибку в файл и базу данных."""
        error_message = f"Error: {str(error)}\nTraceback: {traceback.format_exc()}"
        logger.error(error_message)
        
        # Сохраняем ошибку в базе данных
        await self.db.create_error_log({
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "user_id": context.user_data.get('user_id') if context.user_data else None,
            "chat_id": context.chat_data.get('chat_id') if context.chat_data else None
        })

    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ошибки в обработчиках."""
        error = context.error
        await self.log_error(error, context)
        
        # Отправляем сообщение пользователю
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "😔 Произошла ошибка. Пожалуйста, попробуйте позже или обратитесь к администратору."
            )

def error_handler(func):
    """Декоратор для обработки ошибок в функциях."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Получаем контекст из аргументов
            context = next((arg for arg in args if isinstance(arg, ContextTypes.DEFAULT_TYPE)), None)
            if context:
                handler = ErrorHandler()
                await handler.log_error(e, context)
            
            # Пробрасываем ошибку дальше для обработки глобальным обработчиком
            raise
    return wrapper

class ValidationError(Exception):
    """Исключение для ошибок валидации."""
    pass

def validate_video_duration(duration: int) -> bool:
    """Проверяет длительность видео."""
    if not isinstance(duration, int):
        raise ValidationError("Duration must be an integer")
    if duration <= 0:
        raise ValidationError("Duration must be positive")
    if duration > 60:
        raise ValidationError("Duration must not exceed 60 seconds")
    return True

def validate_challenge_data(data: dict) -> bool:
    """Проверяет данные челленджа."""
    required_fields = ['title', 'description', 'category', 'difficulty']
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    
    if not isinstance(data['difficulty'], int) or not 1 <= data['difficulty'] <= 5:
        raise ValidationError("Difficulty must be an integer between 1 and 5")
    
    if not data['title'].strip():
        raise ValidationError("Title cannot be empty")
    
    if not data['description'].strip():
        raise ValidationError("Description cannot be empty")
    
    return True

def validate_user_data(data: dict) -> bool:
    """Проверяет данные пользователя."""
    required_fields = ['user_id', 'first_name']
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    
    if not isinstance(data['user_id'], int):
        raise ValidationError("User ID must be an integer")
    
    if not data['first_name'].strip():
        raise ValidationError("First name cannot be empty")
    
    return True 