from enum import Enum, auto

class UserStates(Enum):
    # Общие состояния
    MAIN_MENU = auto()
    SETTINGS = auto()
    
    # Онбординг
    ONBOARDING = auto()
    LANGUAGE_SELECTION = auto()
    
    # Челленджи
    VIEWING_CHALLENGES = auto()
    VIEWING_CATEGORY = auto()
    VIEWING_CHALLENGE = auto()
    SENDING_VIDEO = auto()
    CONFIRMING_VIDEO = auto()
    
    # Настройки
    CHANGING_LANGUAGE = auto()
    CHANGING_NOTIFICATIONS = auto()
    
    # Реферальная система
    INVITING_FRIEND = auto()

class AdminStates(Enum):
    # Общие состояния
    MAIN_MENU = auto()
    
    # Модерация
    MODERATING_VIDEOS = auto()
    REJECTING_VIDEO = auto()
    
    # Управление челленджами
    ADDING_CHALLENGE = auto()
    EDITING_CHALLENGE = auto()
    
    # Управление блогерами
    MANAGING_INFLUENCERS = auto()
    ADDING_INFLUENCER = auto()
    EDITING_INFLUENCER = auto()
    
    # Статистика
    VIEWING_STATS = auto()
    SELECTING_STATS_PERIOD = auto()

class InfluencerStates(Enum):
    # Общие состояния
    MAIN_MENU = auto()
    
    # Создание челленджей
    CREATING_CHALLENGE = auto()
    SETTING_CHALLENGE_TITLE = auto()
    SETTING_CHALLENGE_DESCRIPTION = auto()
    UPLOADING_CHALLENGE_MEDIA = auto()
    
    # Статистика
    VIEWING_STATS = auto()
    SELECTING_STATS_PERIOD = auto()
    
    # Управление челленджами
    MANAGING_CHALLENGES = auto()
    EDITING_CHALLENGE = auto()

# Словари для хранения данных состояний
class StateData:
    def __init__(self):
        self.challenge_id = None
        self.video_file_id = None
        self.category = None
        self.page = 1
        self.temp_data = {} 