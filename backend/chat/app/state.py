from __future__ import annotations
from typing import Dict, Any
from uuid import uuid4

# MVP in-memory store: resets on server restart
REPORT_STORE: Dict[str, Dict[str, Any]] = {}


def create_report_session(lipids: Dict[str, float]) -> str:
    report_id = str(uuid4())
    REPORT_STORE[report_id] = {"lipids": lipids}
    return report_id


def get_report_lipids(report_id: str) -> Dict[str, float] | None:
    data = REPORT_STORE.get(report_id)
    if not data:
        return None
    return data.get("lipids")
