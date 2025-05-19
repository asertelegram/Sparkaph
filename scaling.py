import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScalingEvent:
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"

class ScalingSystem:
    def __init__(self):
        self.history = []

    def trigger_scaling(self, event: str, reason: str, data: Optional[Dict[str, Any]] = None):
        record = {
            "event": event,
            "reason": reason,
            "data": data or {},
            "timestamp": datetime.now(UTC)
        }
        self.history.append(record)
        logger.info(f"[SCALING] {event}: {reason}")
        # Здесь должна быть интеграция с облаком/оркестратором
        return True

    def get_status(self) -> Dict[str, Any]:
        # Заглушка: всегда healthy
        return {"status": "healthy", "last_event": self.history[-1] if self.history else None}

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.history[-limit:] 