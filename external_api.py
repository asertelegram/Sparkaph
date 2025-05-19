import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Callable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExternalAPI:
    def __init__(self):
        self.endpoints: Dict[str, Callable] = {}
        self.logs: List[Dict[str, Any]] = []

    def register_endpoint(self, name: str, handler: Callable):
        self.endpoints[name] = handler
        logger.info(f"[API] Зарегистрирован endpoint: {name}")

    def call(self, name: str, *args, **kwargs) -> Any:
        if name not in self.endpoints:
            logger.error(f"[API] Endpoint не найден: {name}")
            return None
        result = self.endpoints[name](*args, **kwargs)
        self.logs.append({
            "endpoint": name,
            "args": args,
            "kwargs": kwargs,
            "result": result,
            "timestamp": datetime.now(UTC)
        })
        return result

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.logs[-limit:]

    def get_stats(self) -> Dict[str, int]:
        return {"total_calls": len(self.logs), "endpoints": len(self.endpoints)} 