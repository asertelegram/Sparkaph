import os
import logging
from typing import Optional, Dict, Any
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

class SocialMediaManager:
    def __init__(self):
        self.tiktok_api_key = os.getenv("TIKTOK_API_KEY")
        self.instagram_api_key = os.getenv("INSTAGRAM_API_KEY")
        self.tiktok_api_url = "https://open.tiktokapis.com/v2"
        self.instagram_api_url = "https://graph.instagram.com/v12.0"
        
        if not self.tiktok_api_key or not self.instagram_api_key:
            logger.warning("API ключи для социальных сетей не найдены")
    
    async def post_to_tiktok(self, video_path: str, caption: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Публикация видео в TikTok"""
        try:
            if not self.tiktok_api_key:
                logger.error("TikTok API ключ не настроен")
                return None
            
            headers = {
                "Authorization": f"Bearer {self.tiktok_api_key}",
                "Content-Type": "application/json"
            }
            
            # Загружаем видео
            async with aiohttp.ClientSession() as session:
                # Сначала получаем URL для загрузки
                upload_url_response = await session.post(
                    f"{self.tiktok_api_url}/video/upload/",
                    headers=headers
                )
                
                if upload_url_response.status != 200:
                    logger.error(f"Ошибка получения URL для загрузки: {await upload_url_response.text()}")
                    return None
                
                upload_data = await upload_url_response.json()
                upload_url = upload_data["upload_url"]
                
                # Загружаем видео
                with open(video_path, "rb") as video_file:
                    upload_response = await session.put(
                        upload_url,
                        data=video_file,
                        headers={"Content-Type": "video/mp4"}
                    )
                    
                    if upload_response.status != 200:
                        logger.error(f"Ошибка загрузки видео: {await upload_response.text()}")
                        return None
                
                # Публикуем видео
                publish_data = {
                    "video_id": upload_data["video_id"],
                    "caption": caption,
                    "user_id": user_id
                }
                
                publish_response = await session.post(
                    f"{self.tiktok_api_url}/video/publish/",
                    headers=headers,
                    json=publish_data
                )
                
                if publish_response.status != 200:
                    logger.error(f"Ошибка публикации видео: {await publish_response.text()}")
                    return None
                
                return await publish_response.json()
                
        except Exception as e:
            logger.error(f"Ошибка при публикации в TikTok: {e}")
            return None
    
    async def post_to_instagram(self, media_path: str, caption: str, user_id: int, is_story: bool = False) -> Optional[Dict[str, Any]]:
        """Публикация медиа в Instagram"""
        try:
            if not self.instagram_api_key:
                logger.error("Instagram API ключ не настроен")
                return None
            
            headers = {
                "Authorization": f"Bearer {self.instagram_api_key}",
                "Content-Type": "application/json"
            }
            
            # Определяем тип медиа
            media_type = "IMAGE" if media_path.lower().endswith((".jpg", ".jpeg", ".png")) else "VIDEO"
            
            async with aiohttp.ClientSession() as session:
                # Создаем контейнер для медиа
                container_data = {
                    "media_type": media_type,
                    "caption": caption,
                    "user_id": user_id
                }
                
                if is_story:
                    container_data["story_type"] = "STORY"
                
                container_response = await session.post(
                    f"{self.instagram_api_url}/media/container",
                    headers=headers,
                    json=container_data
                )
                
                if container_response.status != 200:
                    logger.error(f"Ошибка создания контейнера: {await container_response.text()}")
                    return None
                
                container_data = await container_response.json()
                container_id = container_data["id"]
                
                # Загружаем медиа
                with open(media_path, "rb") as media_file:
                    upload_response = await session.post(
                        f"{self.instagram_api_url}/media/upload",
                        headers=headers,
                        data={"media": media_file}
                    )
                    
                    if upload_response.status != 200:
                        logger.error(f"Ошибка загрузки медиа: {await upload_response.text()}")
                        return None
                
                # Публикуем медиа
                publish_response = await session.post(
                    f"{self.instagram_api_url}/media/publish",
                    headers=headers,
                    json={"creation_id": container_id}
                )
                
                if publish_response.status != 200:
                    logger.error(f"Ошибка публикации медиа: {await publish_response.text()}")
                    return None
                
                return await publish_response.json()
                
        except Exception as e:
            logger.error(f"Ошибка при публикации в Instagram: {e}")
            return None
    
    async def get_media_insights(self, media_id: str, platform: str) -> Optional[Dict[str, Any]]:
        """Получение статистики по медиа"""
        try:
            if platform.lower() == "tiktok":
                api_url = f"{self.tiktok_api_url}/video/stats/{media_id}"
                headers = {"Authorization": f"Bearer {self.tiktok_api_key}"}
            elif platform.lower() == "instagram":
                api_url = f"{self.instagram_api_url}/media/{media_id}/insights"
                headers = {"Authorization": f"Bearer {self.instagram_api_key}"}
            else:
                logger.error(f"Неподдерживаемая платформа: {platform}")
                return None
            
            async with aiohttp.ClientSession() as session:
                response = await session.get(api_url, headers=headers)
                
                if response.status != 200:
                    logger.error(f"Ошибка получения статистики: {await response.text()}")
                    return None
                
                return await response.json()
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return None

# Создаем глобальный экземпляр менеджера социальных сетей
social_media_manager = SocialMediaManager() 