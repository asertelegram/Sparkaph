import pytest
import os
from unittest.mock import patch, MagicMock
from social_media import SocialMediaManager

@pytest.fixture
def social_media_manager():
    return SocialMediaManager()

@pytest.fixture
def mock_video_file(tmp_path):
    video_path = tmp_path / "test_video.mp4"
    video_path.write_bytes(b"fake video content")
    return str(video_path)

@pytest.fixture
def mock_image_file(tmp_path):
    image_path = tmp_path / "test_image.jpg"
    image_path.write_bytes(b"fake image content")
    return str(image_path)

@pytest.mark.asyncio
async def test_post_to_tiktok_success(social_media_manager, mock_video_file):
    """Тест успешной публикации в TikTok"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "video_id": "123456",
        "status": "success"
    }
    
    with patch("aiohttp.ClientSession.post", return_value=mock_response) as mock_post, \
         patch("aiohttp.ClientSession.put", return_value=mock_response):
        
        result = await social_media_manager.post_to_tiktok(
            video_path=mock_video_file,
            caption="Test caption",
            user_id=123456
        )
        
        assert result is not None
        assert result["video_id"] == "123456"
        assert result["status"] == "success"

@pytest.mark.asyncio
async def test_post_to_tiktok_failure(social_media_manager, mock_video_file):
    """Тест неудачной публикации в TikTok"""
    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.text.return_value = "Error message"
    
    with patch("aiohttp.ClientSession.post", return_value=mock_response):
        result = await social_media_manager.post_to_tiktok(
            video_path=mock_video_file,
            caption="Test caption",
            user_id=123456
        )
        
        assert result is None

@pytest.mark.asyncio
async def test_post_to_instagram_success(social_media_manager, mock_image_file):
    """Тест успешной публикации в Instagram"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "id": "123456",
        "status": "success"
    }
    
    with patch("aiohttp.ClientSession.post", return_value=mock_response):
        result = await social_media_manager.post_to_instagram(
            media_path=mock_image_file,
            caption="Test caption",
            user_id=123456,
            is_story=False
        )
        
        assert result is not None
        assert result["id"] == "123456"
        assert result["status"] == "success"

@pytest.mark.asyncio
async def test_post_to_instagram_story(social_media_manager, mock_image_file):
    """Тест публикации в Instagram Stories"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "id": "123456",
        "status": "success"
    }
    
    with patch("aiohttp.ClientSession.post", return_value=mock_response):
        result = await social_media_manager.post_to_instagram(
            media_path=mock_image_file,
            caption="Test caption",
            user_id=123456,
            is_story=True
        )
        
        assert result is not None
        assert result["id"] == "123456"
        assert result["status"] == "success"

@pytest.mark.asyncio
async def test_get_media_insights_tiktok(social_media_manager):
    """Тест получения статистики TikTok"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "views": 1000,
        "likes": 100,
        "comments": 50
    }
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        result = await social_media_manager.get_media_insights(
            media_id="123456",
            platform="tiktok"
        )
        
        assert result is not None
        assert result["views"] == 1000
        assert result["likes"] == 100
        assert result["comments"] == 50

@pytest.mark.asyncio
async def test_get_media_insights_instagram(social_media_manager):
    """Тест получения статистики Instagram"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "impressions": 2000,
        "reach": 1500,
        "saved": 100
    }
    
    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        result = await social_media_manager.get_media_insights(
            media_id="123456",
            platform="instagram"
        )
        
        assert result is not None
        assert result["impressions"] == 2000
        assert result["reach"] == 1500
        assert result["saved"] == 100

@pytest.mark.asyncio
async def test_get_media_insights_invalid_platform(social_media_manager):
    """Тест получения статистики с неподдерживаемой платформой"""
    result = await social_media_manager.get_media_insights(
        media_id="123456",
        platform="facebook"
    )
    
    assert result is None

def test_social_media_manager_initialization():
    """Тест инициализации менеджера социальных сетей"""
    with patch.dict(os.environ, {
        "TIKTOK_API_KEY": "test_tiktok_key",
        "INSTAGRAM_API_KEY": "test_instagram_key"
    }):
        manager = SocialMediaManager()
        assert manager.tiktok_api_key == "test_tiktok_key"
        assert manager.instagram_api_key == "test_instagram_key"

def test_social_media_manager_missing_api_keys():
    """Тест инициализации менеджера без API ключей"""
    with patch.dict(os.environ, {}, clear=True):
        manager = SocialMediaManager()
        assert manager.tiktok_api_key is None
        assert manager.instagram_api_key is None 