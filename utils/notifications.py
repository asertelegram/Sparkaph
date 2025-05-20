from telegram import Bot
from database.operations import Database
from config import USER_BOT_TOKEN

class NotificationManager:
    def __init__(self):
        self.bot = Bot(token=USER_BOT_TOKEN)
        self.db = Database()

    async def send_notification(self, user_id: int, message: str):
        """Отправляет уведомление пользователю."""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message
            )
            # Сохраняем уведомление в базе
            await self.db.create_notification({
                "user_id": user_id,
                "type": "custom",
                "message": message
            })
        except Exception as e:
            print(f"Error sending notification to {user_id}: {e}")

    async def notify_video_approved(self, user_id: int, challenge_title: str):
        """Уведомляет о одобрении видео."""
        message = f"✅ Ваше видео для челленджа '{challenge_title}' было одобрено!"
        await self.send_notification(user_id, message)

    async def notify_video_rejected(self, user_id: int, challenge_title: str, reason: str):
        """Уведомляет об отклонении видео."""
        message = f"❌ Ваше видео для челленджа '{challenge_title}' было отклонено.\nПричина: {reason}"
        await self.send_notification(user_id, message)

    async def notify_new_challenge(self, user_id: int, challenge_title: str):
        """Уведомляет о новом челлендже."""
        message = f"🎯 Новый челлендж: '{challenge_title}'!\nПопробуйте выполнить его первым!"
        await self.send_notification(user_id, message)

    async def notify_achievement(self, user_id: int, badge_name: str):
        """Уведомляет о получении достижения."""
        message = f"🏆 Поздравляем! Вы получили бейдж: {badge_name}"
        await self.send_notification(user_id, message)

    async def notify_referral(self, user_id: int, referred_user_name: str):
        """Уведомляет о приглашении нового пользователя."""
        message = f"👥 Пользователь {referred_user_name} присоединился по вашей реферальной ссылке!"
        await self.send_notification(user_id, message)

    async def notify_challenge_completed(self, user_id: int, challenge_title: str):
        """Уведомляет о завершении челленджа."""
        message = f"🎉 Поздравляем! Вы завершили челлендж '{challenge_title}'!"
        await self.send_notification(user_id, message) 