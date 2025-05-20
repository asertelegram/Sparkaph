from telegram import Bot
from database.operations import Database
from config import CHANNEL_ID, USER_BOT_TOKEN
from utils.notifications import NotificationManager

class ChannelManager:
    def __init__(self):
        self.bot = Bot(token=USER_BOT_TOKEN)
        self.db = Database()
        self.notifications = NotificationManager()

    async def publish_video(self, video_file_id: str, caption: str, user_id: int, challenge_id: int):
        """Публикует видео в канале."""
        try:
            # Отправляем видео в канал
            message = await self.bot.send_video(
                chat_id=CHANNEL_ID,
                video=video_file_id,
                caption=caption
            )
            
            # Обновляем информацию о видео в базе
            await self.db.update_submission_status(
                submission_id=challenge_id,
                status="published",
                channel_message_id=message.message_id
            )
            
            # Уведомляем пользователя
            challenge = await self.db.get_challenge(challenge_id)
            if challenge:
                await self.notifications.notify_video_approved(
                    user_id=user_id,
                    challenge_title=challenge.title
                )
            
            return message.message_id
        except Exception as e:
            print(f"Error publishing video: {e}")
            return None

    async def update_video_stats(self, message_id: int):
        """Обновляет статистику видео (просмотры, лайки)."""
        try:
            # Получаем информацию о сообщении
            message = await self.bot.get_message(
                chat_id=CHANNEL_ID,
                message_id=message_id
            )
            
            # Обновляем статистику в базе
            await self.db.update_submission_stats(
                submission_id=message_id,
                views_count=message.views,
                likes_count=message.likes
            )
        except Exception as e:
            print(f"Error updating video stats: {e}")

    async def delete_video(self, message_id: int):
        """Удаляет видео из канала."""
        try:
            await self.bot.delete_message(
                chat_id=CHANNEL_ID,
                message_id=message_id
            )
        except Exception as e:
            print(f"Error deleting video: {e}")

    async def pin_video(self, message_id: int):
        """Закрепляет видео в канале."""
        try:
            await self.bot.pin_chat_message(
                chat_id=CHANNEL_ID,
                message_id=message_id
            )
        except Exception as e:
            print(f"Error pinning video: {e}")

    async def unpin_video(self, message_id: int):
        """Открепляет видео в канале."""
        try:
            await self.bot.unpin_chat_message(
                chat_id=CHANNEL_ID,
                message_id=message_id
            )
        except Exception as e:
            print(f"Error unpinning video: {e}")

    async def get_channel_stats(self):
        """Получает статистику канала."""
        try:
            chat = await self.bot.get_chat(CHANNEL_ID)
            return {
                "subscribers": chat.members_count,
                "description": chat.description,
                "title": chat.title
            }
        except Exception as e:
            print(f"Error getting channel stats: {e}")
            return None 