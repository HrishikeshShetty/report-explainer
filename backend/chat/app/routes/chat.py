from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict

from app.services.chat_engine import ChatEngine
from app.state import create_report_session, get_report_lipids

router = APIRouter()
engine = ChatEngine()


class ChatRequest(BaseModel):
    question: str
    lipids: Optional[Dict[str, float]] = None
    report_id: Optional[str] = None


@router.post("/ask")
def ask_question(payload: ChatRequest):
    # Case 1: New session (lipids provided)
    if payload.lipids:
        report_id = create_report_session(payload.lipids)
        result = engine.answer(payload.question, payload.lipids)
        result["report_id"] = report_id
        return result

    # Case 2: Existing session
    if payload.report_id:
        lipids = get_report_lipids(payload.report_id)
        if not lipids:
            raise HTTPException(status_code=404, detail="Invalid report_id")
        result = engine.answer(payload.question, lipids)
        result["report_id"] = payload.report_id
        return result

    raise HTTPException(status_code=400, detail="Provide lipids or report_id")
