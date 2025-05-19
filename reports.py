import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportSystem:
    def __init__(self):
        self.reports: List[Dict[str, Any]] = []

    def generate_report(self, report_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        report = {
            "id": len(self.reports) + 1,
            "type": report_type,
            "data": data,
            "created_at": datetime.now(UTC)
        }
        self.reports.append(report)
        logger.info(f"[REPORT] Сгенерирован отчет: {report_type}")
        return report

    def get_reports(self, report_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        reports = self.reports
        if report_type:
            reports = [r for r in reports if r["type"] == report_type]
        return reports[-limit:]

    def get_stats(self) -> Dict[str, int]:
        return {"total": len(self.reports), "by_type": {t: len([r for r in self.reports if r["type"] == t]) for t in set(r["type"] for r in self.reports)}} 