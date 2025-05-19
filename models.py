from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Модель пользователя
class User(BaseModel):
    user_id: int
    username: Optional[str]
    points: int = 0
    level: int = 1
    completed_challenges: List[str] = []  # id выполненных челленджей
    referrals: List[int] = []  # user_id приглашённых
    registration_date: datetime = Field(default_factory=datetime.utcnow)
    achievements: List[str] = []
    streak: int = 0  # серия дней
    last_active: Optional[datetime] = None

# Модель челленджа
class Challenge(BaseModel):
    challenge_id: str
    category_id: str
    author_id: Optional[int] = None  # id инфлюенсера или None
    title: str
    description: str
    points: int = 10
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    media_url: Optional[str] = None  # ссылка на поясняющее видео

# Модель категории
class Category(BaseModel):
    category_id: str
    name: str
    is_public: bool = True
    influencer_id: Optional[int] = None  # если категория для инфлюенсера
    description: Optional[str] = None

# Модель отчёта пользователя по челленджу
class Report(BaseModel):
    report_id: str
    user_id: int
    challenge_id: str
    file_type: str  # video/photo/text
    file_url: Optional[str] = None
    status: str = "pending"  # pending/approved/rejected
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    published_url: Optional[str] = None  # ссылка на публикацию в соцсети

# Модель реферала
class Referral(BaseModel):
    inviter_id: int
    invited_id: int
    activated: bool = False
    activated_at: Optional[datetime] = None 