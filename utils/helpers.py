import random
import string
from datetime import datetime, timedelta
from typing import List, Optional
from config import BADGES

def generate_referral_code(length: int = 8) -> str:
    """Генерирует уникальный реферальный код."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def calculate_streak_days(last_active: datetime) -> int:
    """Рассчитывает количество дней подряд активности."""
    today = datetime.utcnow().date()
    last_active_date = last_active.date()
    
    if today == last_active_date:
        return 1
    elif today - last_active_date == timedelta(days=1):
        return 2
    return 0

def get_streak_badge(streak_days: int) -> Optional[str]:
    """Возвращает бейдж за серию дней активности."""
    if streak_days >= 30:
        return "streak_30"
    elif streak_days >= 7:
        return "streak_7"
    elif streak_days >= 3:
        return "streak_3"
    return None

def format_leaderboard_entry(entry: dict, position: int) -> str:
    """Форматирует запись для лидерборда."""
    return f"{position}. {entry['username'] or 'Аноним'} - {entry['points']} очков"

def format_challenge_info(challenge: dict) -> str:
    """Форматирует информацию о челлендже."""
    return f"""
🎯 {challenge['title']}

📝 {challenge['description']}

🏷 Категория: {challenge['category']}
⭐ Сложность: {'⭐' * challenge['difficulty']}
👥 Участников: {challenge['completions_count']}
👁 Просмотров: {challenge['views_count']}
"""

def format_user_stats(stats: dict) -> str:
    """Форматирует статистику пользователя."""
    badges_text = "\n".join([BADGES[badge] for badge in stats['badges']]) if stats['badges'] else "Нет бейджей"
    
    return f"""
📊 Ваша статистика:

✅ Завершено челленджей: {stats['completed_challenges']}
📱 Отправлено видео: {stats['total_submissions']}
✅ Одобрено видео: {stats['approved_submissions']}
🔥 Дней подряд: {stats['streak_days']}

🏆 Ваши бейджи:
{badges_text}
"""

def format_challenge_stats(stats: dict) -> str:
    """Форматирует статистику челленджа."""
    return f"""
📊 Статистика челленджа:

👁 Просмотров: {stats['views']}
✅ Завершений: {stats['completions']}
📱 Отправлено видео: {stats['submissions']}
✅ Одобрено видео: {stats['approved_submissions']}
"""

def get_random_challenge(challenges: List[dict]) -> Optional[dict]:
    """Возвращает случайный челлендж из списка."""
    if not challenges:
        return None
    return random.choice(challenges)

def format_time_ago(dt: datetime) -> str:
    """Форматирует время в формат 'X времени назад'."""
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} {'год' if years == 1 else 'года' if 1 < years < 5 else 'лет'} назад"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} {'месяц' if months == 1 else 'месяца' if 1 < months < 5 else 'месяцев'} назад"
    elif diff.days > 0:
        return f"{diff.days} {'день' if diff.days == 1 else 'дня' if 1 < diff.days < 5 else 'дней'} назад"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} {'час' if hours == 1 else 'часа' if 1 < hours < 5 else 'часов'} назад"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} {'минуту' if minutes == 1 else 'минуты' if 1 < minutes < 5 else 'минут'} назад"
    else:
        return "только что"

def validate_video_duration(duration: int) -> bool:
    """Проверяет длительность видео (максимум 60 секунд)."""
    return 0 < duration <= 60

def get_pagination_info(items: List, page: int, per_page: int = 10) -> dict:
    """Возвращает информацию для пагинации."""
    total_items = len(items)
    total_pages = (total_items + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_items)
    
    return {
        "items": items[start_idx:end_idx],
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "has_next": page < total_pages,
        "has_prev": page > 1
    } 