import os
from typing import Optional, Dict, Any
import aiohttp
from datetime import datetime
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class TikTokAPI:
    def __init__(self):
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        self.redirect_uri = os.getenv("TIKTOK_REDIRECT_URI")
        self.api_base_url = "https://open.tiktokapis.com/v2"
        self.access_token = None
    
    async def get_auth_url(self) -> str:
        """Получить URL для авторизации"""
        return f"https://www.tiktok.com/auth/authorize/?client_key={self.client_key}&scope=user.info.basic,video.list&response_type=code&redirect_uri={self.redirect_uri}"
    
    async def get_access_token(self, code: str) -> Dict[str, Any]:
        """Получить access token"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/oauth/token/",
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data["access_token"]
                    return data
                else:
                    raise Exception(f"Failed to get access token: {await response.text()}")
    
    async def get_user_info(self) -> Dict[str, Any]:
        """Получить информацию о пользователе"""
        if not self.access_token:
            raise Exception("Access token not set")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_base_url}/user/info/",
                headers={"Authorization": f"Bearer {self.access_token}"}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get user info: {await response.text()}")
    
    async def post_video(self, video_path: str, description: str) -> Dict[str, Any]:
        """Опубликовать видео"""
        if not self.access_token:
            raise Exception("Access token not set")
        
        # Сначала загружаем видео
        async with aiohttp.ClientSession() as session:
            with open(video_path, 'rb') as f:
                video_data = f.read()
            
            async with session.post(
                f"{self.api_base_url}/video/upload/",
                headers={"Authorization": f"Bearer {self.access_token}"},
                data={"video": video_data}
            ) as response:
                if response.status == 200:
                    upload_data = await response.json()
                    video_id = upload_data["video_id"]
                    
                    # Теперь публикуем видео
                    async with session.post(
                        f"{self.api_base_url}/video/publish/",
                        headers={"Authorization": f"Bearer {self.access_token}"},
                        json={
                            "video_id": video_id,
                            "description": description
                        }
                    ) as publish_response:
                        if publish_response.status == 200:
                            return await publish_response.json()
                        else:
                            raise Exception(f"Failed to publish video: {await publish_response.text()}")
                else:
                    raise Exception(f"Failed to upload video: {await response.text()}")

class InstagramAPI:
    def __init__(self):
        self.client_id = os.getenv("INSTAGRAM_CLIENT_ID")
        self.client_secret = os.getenv("INSTAGRAM_CLIENT_SECRET")
        self.redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI")
        self.api_base_url = "https://graph.instagram.com"
        self.access_token = None
    
    async def get_auth_url(self) -> str:
        """Получить URL для авторизации"""
        return f"https://api.instagram.com/oauth/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope=user_profile,user_media&response_type=code"
    
    async def get_access_token(self, code: str) -> Dict[str, Any]:
        """Получить access token"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code": code
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data["access_token"]
                    return data
                else:
                    raise Exception(f"Failed to get access token: {await response.text()}")
    
    async def get_user_info(self) -> Dict[str, Any]:
        """Получить информацию о пользователе"""
        if not self.access_token:
            raise Exception("Access token not set")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_base_url}/me",
                params={
                    "fields": "id,username,account_type",
                    "access_token": self.access_token
                }
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get user info: {await response.text()}")
    
    async def post_media(self, media_path: str, caption: str) -> Dict[str, Any]:
        """Опубликовать медиа"""
        if not self.access_token:
            raise Exception("Access token not set")
        
        # Создаем контейнер для медиа
        async with aiohttp.ClientSession() as session:
            with open(media_path, 'rb') as f:
                media_data = f.read()
            
            # Загружаем медиа
            async with session.post(
                f"{self.api_base_url}/me/media",
                params={"access_token": self.access_token},
                data={
                    "image_url": media_path,  # URL медиа
                    "caption": caption,
                    "media_type": "IMAGE"
                }
            ) as response:
                if response.status == 200:
                    media_data = await response.json()
                    media_id = media_data["id"]
                    
                    # Публикуем медиа
                    async with session.post(
                        f"{self.api_base_url}/me/media_publish",
                        params={
                            "access_token": self.access_token,
                            "creation_id": media_id
                        }
                    ) as publish_response:
                        if publish_response.status == 200:
                            return await publish_response.json()
                        else:
                            raise Exception(f"Failed to publish media: {await publish_response.text()}")
                else:
                    raise Exception(f"Failed to create media container: {await response.text()}")

# Создаем экземпляры API
tiktok_api = TikTokAPI()
instagram_api = InstagramAPI()

async def get_social_auth_urls() -> Dict[str, str]:
    """Получить URLs для авторизации в социальных сетях"""
    return {
        "tiktok": await tiktok_api.get_auth_url(),
        "instagram": await instagram_api.get_auth_url()
    }

async def handle_social_auth(platform: str, code: str) -> Dict[str, Any]:
    """Обработать авторизацию в социальной сети"""
    if platform == "tiktok":
        return await tiktok_api.get_access_token(code)
    elif platform == "instagram":
        return await instagram_api.get_access_token(code)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

async def post_to_social(platform: str, media_path: str, description: str) -> Dict[str, Any]:
    """Опубликовать контент в социальной сети"""
    if platform == "tiktok":
        return await tiktok_api.post_video(media_path, description)
    elif platform == "instagram":
        return await instagram_api.post_media(media_path, description)
    else:
        raise ValueError(f"Unsupported platform: {platform}") 