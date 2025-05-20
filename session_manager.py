import logging
import aiohttp
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.sessions = {}
    
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

session_manager = SessionManager() 