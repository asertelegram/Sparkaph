import logging
import aiohttp
from contextlib import asynccontextmanager
import asyncio

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self._cleanup_task = None
    
    @asynccontextmanager
    async def get_session(self, bot_type: str):
        if bot_type not in self.sessions:
            self.sessions[bot_type] = aiohttp.ClientSession()
        
        try:
            yield self.sessions[bot_type]
        except Exception as e:
            logger.error(f"Error in session for {bot_type}: {e}")
            raise
    
    async def close_all(self):
        for bot_type, session in self.sessions.items():
            try:
                if not session.closed:
                    await session.close()
            except Exception as e:
                logger.error(f"Error closing session for {bot_type}: {e}")
    
    async def start_cleanup(self):
        """Запускает периодическую очистку сессий"""
        while True:
            try:
                await self.close_all()
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
            await asyncio.sleep(300)  # Проверяем каждые 5 минут
    
    def start(self):
        """Запускает менеджер сессий"""
        self._cleanup_task = asyncio.create_task(self.start_cleanup())
    
    async def stop(self):
        """Останавливает менеджер сессий"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        await self.close_all()

session_manager = SessionManager() 