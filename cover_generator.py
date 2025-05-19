import os
import logging
from typing import Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from datetime import datetime
from bson import ObjectId

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoverGenerator:
    def __init__(self):
        self.temp_dir = "temp_media"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Загружаем шрифты
        self.fonts_dir = "fonts"
        os.makedirs(self.fonts_dir, exist_ok=True)
        
        # Создаем базовые шрифты, если их нет
        self.default_font = ImageFont.load_default()
        
        # Стили обложек
        self.styles = {
            "modern": {
                "background_color": (255, 255, 255),
                "text_color": (0, 0, 0),
                "accent_color": (41, 128, 185),
                "overlay_opacity": 0.3
            },
            "dark": {
                "background_color": (44, 62, 80),
                "text_color": (255, 255, 255),
                "accent_color": (52, 152, 219),
                "overlay_opacity": 0.5
            },
            "gradient": {
                "background_color": (255, 255, 255),
                "text_color": (255, 255, 255),
                "accent_color": (231, 76, 60),
                "overlay_opacity": 0.4
            }
        }
    
    async def generate_cover(
        self,
        submission: dict,
        format_type: str,
        style: str = "modern",
        text: Optional[str] = None
    ) -> Optional[bytes]:
        """Генерация обложки для медиа"""
        try:
            if not submission.get("file_content"):
                logger.error("Нет содержимого файла в submission")
                return None
            
            # Декодируем base64 в байты
            image_bytes = base64.b64decode(submission["file_content"])
            image = Image.open(io.BytesIO(image_bytes))
            
            # Определяем размеры для разных форматов
            if format_type in ["tiktok", "insta_story"]:
                # 9:16 формат (1080x1920)
                target_width = 1080
                target_height = 1920
            else:  # insta_post
                # 1:1 формат (1080x1080)
                target_width = 1080
                target_height = 1080
            
            # Получаем стиль
            style_config = self.styles.get(style, self.styles["modern"])
            
            # Создаем новое изображение с нужным размером
            new_image = Image.new("RGB", (target_width, target_height), style_config["background_color"])
            
            # Изменяем размер исходного изображения, сохраняя пропорции
            image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Вычисляем позицию для центрирования
            x = (target_width - image.width) // 2
            y = (target_height - image.height) // 2
            
            # Создаем оверлей для текста
            overlay = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Добавляем текст, если он есть
            if text:
                # Разбиваем текст на строки
                words = text.split()
                lines = []
                current_line = []
                
                for word in words:
                    current_line.append(word)
                    # Проверяем ширину текущей строки
                    line_width = draw.textlength(" ".join(current_line), font=self.default_font)
                    if line_width > target_width * 0.8:  # 80% от ширины изображения
                        current_line.pop()
                        lines.append(" ".join(current_line))
                        current_line = [word]
                
                if current_line:
                    lines.append(" ".join(current_line))
                
                # Рисуем каждую строку
                y_text = target_height * 0.7  # Начинаем с 70% высоты
                for line in lines:
                    # Рисуем тень
                    draw.text(
                        (x + 2, y_text + 2),
                        line,
                        font=self.default_font,
                        fill=(0, 0, 0, 128)
                    )
                    # Рисуем текст
                    draw.text(
                        (x, y_text),
                        line,
                        font=self.default_font,
                        fill=style_config["text_color"]
                    )
                    y_text += 40  # Отступ между строками
            
            # Вставляем изображение
            new_image.paste(image, (x, y))
            
            # Накладываем оверлей
            new_image = Image.alpha_composite(new_image.convert("RGBA"), overlay)
            
            # Сохраняем в байты
            output = io.BytesIO()
            new_image.save(output, format="JPEG", quality=95)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации обложки: {e}")
            return None
    
    async def generate_preview(
        self,
        submission: dict,
        format_type: str,
        style: str = "modern"
    ) -> Optional[bytes]:
        """Генерация превью обложки"""
        try:
            # Генерируем обложку с тестовым текстом
            return await self.generate_cover(
                submission=submission,
                format_type=format_type,
                style=style,
                text="Тестовая обложка"
            )
        except Exception as e:
            logger.error(f"Ошибка при генерации превью: {e}")
            return None
    
    def get_available_styles(self) -> List[str]:
        """Получение списка доступных стилей"""
        return list(self.styles.keys())
    
    def get_available_formats(self) -> List[str]:
        """Получение списка доступных форматов"""
        return ["tiktok", "insta_story", "insta_post"]

# Создаем глобальный экземпляр генератора обложек
cover_generator = CoverGenerator() 