import pytest
from datetime import datetime, timedelta
from models import User
from achievements import Achievement, AchievementSystem

@pytest.fixture
def achievement_system():
    return AchievementSystem()

@pytest.fixture
def new_user():
    return User(
        user_id=123456789,
        username="test_user",
        points=0,
        level=1,
        completed_challenges=[],
        referrals=[],
        registration_date=datetime.utcnow(),
        achievements=[],
        streak=0
    )

@pytest.fixture
def experienced_user():
    return User(
        user_id=987654321,
        username="experienced_user",
        points=500,
        level=5,
        completed_challenges=["challenge1", "challenge2", "challenge3"],
        referrals=[111111111, 222222222],
        registration_date=datetime.utcnow() - timedelta(days=30),
        achievements=["first_challenge", "streak_3"],
        streak=5
    )

def test_achievement_creation():
    """Тест создания достижения"""
    achievement = Achievement(
        id="test_achievement",
        name="Test Achievement",
        description="Test Description",
        points=10,
        condition=lambda user: True,
        icon="🎯"
    )
    
    assert achievement.id == "test_achievement"
    assert achievement.name == "Test Achievement"
    assert achievement.description == "Test Description"
    assert achievement.points == 10
    assert achievement.icon == "🎯"

def test_achievement_system_initialization(achievement_system):
    """Тест инициализации системы достижений"""
    assert len(achievement_system.achievements) > 0
    assert "first_challenge" in achievement_system.achievements
    assert "challenge_master" in achievement_system.achievements
    assert "streak_3" in achievement_system.achievements

@pytest.mark.asyncio
async def test_check_achievements_new_user(achievement_system, new_user):
    """Тест проверки достижений для нового пользователя"""
    new_achievements = await achievement_system.check_achievements(new_user)
    assert len(new_achievements) == 0

@pytest.mark.asyncio
async def test_check_achievements_first_challenge(achievement_system, new_user):
    """Тест получения достижения за первый челлендж"""
    new_user.completed_challenges = ["challenge1"]
    new_achievements = await achievement_system.check_achievements(new_user)
    
    assert len(new_achievements) == 1
    assert new_achievements[0].id == "first_challenge"
    assert new_user.points == 5  # Очки за первое достижение

@pytest.mark.asyncio
async def test_check_achievements_streak(achievement_system, new_user):
    """Тест получения достижений за серию дней"""
    new_user.streak = 3
    new_achievements = await achievement_system.check_achievements(new_user)
    
    assert len(new_achievements) == 1
    assert new_achievements[0].id == "streak_3"
    assert new_user.points == 10  # Очки за достижение серии

@pytest.mark.asyncio
async def test_check_achievements_multiple(achievement_system, experienced_user):
    """Тест получения нескольких достижений одновременно"""
    experienced_user.points = 1000
    experienced_user.streak = 7
    new_achievements = await achievement_system.check_achievements(experienced_user)
    
    assert len(new_achievements) >= 2
    achievement_ids = [a.id for a in new_achievements]
    assert "points_1000" in achievement_ids
    assert "streak_7" in achievement_ids

def test_get_achievement(achievement_system):
    """Тест получения достижения по ID"""
    achievement = achievement_system.get_achievement("first_challenge")
    assert achievement is not None
    assert achievement.id == "first_challenge"
    
    # Проверка несуществующего достижения
    achievement = achievement_system.get_achievement("non_existent")
    assert achievement is None

def test_get_all_achievements(achievement_system):
    """Тест получения всех достижений"""
    achievements = achievement_system.get_all_achievements()
    assert len(achievements) > 0
    assert all(isinstance(a, Achievement) for a in achievements)

def test_get_user_achievements(achievement_system, experienced_user):
    """Тест получения достижений пользователя"""
    user_achievements = achievement_system.get_user_achievements(experienced_user)
    assert len(user_achievements) == 2
    assert all(a.id in experienced_user.achievements for a in user_achievements)

def test_format_achievement(achievement_system):
    """Тест форматирования достижения"""
    achievement = achievement_system.get_achievement("first_challenge")
    formatted = achievement_system.format_achievement(achievement)
    
    assert achievement.name in formatted
    assert achievement.description in formatted
    assert str(achievement.points) in formatted
    assert achievement.icon in formatted

def test_format_achievements_list(achievement_system, experienced_user):
    """Тест форматирования списка достижений"""
    user_achievements = achievement_system.get_user_achievements(experienced_user)
    formatted = achievement_system.format_achievements_list(user_achievements)
    
    assert len(formatted.split("\n\n")) == len(user_achievements)
    for achievement in user_achievements:
        assert achievement.name in formatted
        assert achievement.description in formatted

def test_empty_achievements_list(achievement_system):
    """Тест форматирования пустого списка достижений"""
    formatted = achievement_system.format_achievements_list([])
    assert formatted == "У вас пока нет достижений" 