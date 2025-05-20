from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class User(BaseModel):
    user_id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    language_code: str = "ru"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
    badges: List[str] = []
    completed_challenges: List[int] = []
    streak_days: int = 0
    referral_code: str
    referred_by: Optional[int] = None
    is_influencer: bool = False
    influencer_category: Optional[str] = None

class Challenge(BaseModel):
    challenge_id: int
    title: str
    description: str
    category: str
    created_by: int  # user_id создателя
    created_at: datetime = Field(default_factory=datetime.utcnow)
    difficulty: int = 1  # 1-5
    tags: List[str] = []
    is_active: bool = True
    views_count: int = 0
    completions_count: int = 0
    media_url: Optional[str] = None  # URL примера выполнения

class VideoSubmission(BaseModel):
    submission_id: int
    user_id: int
    challenge_id: int
    video_file_id: str
    status: str = "pending"  # pending, approved, rejected
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    moderated_at: Optional[datetime] = None
    moderator_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    channel_message_id: Optional[int] = None
    likes_count: int = 0
    views_count: int = 0

class LeaderboardEntry(BaseModel):
    user_id: int
    username: Optional[str]
    points: int = 0
    completed_challenges: int = 0
    streak_days: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class Notification(BaseModel):
    user_id: int
    type: str  # challenge_new, video_approved, video_rejected, etc.
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_read: bool = False
    data: dict = {}  # Дополнительные данные для разных типов уведомлений 