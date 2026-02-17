from fastapi import APIRouter
from pydantic import BaseModel
from app.services.chat_engine import ChatEngine
import math

router = APIRouter()
engine = ChatEngine()

class ChatRequest(BaseModel):
    question: str
    lipids: dict


# ---- FIX: JSON safe converter ----
def make_json_safe(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    return obj


@router.post("/ask")
def ask_question(payload: ChatRequest):
    result = engine.answer(payload.question, payload.lipids)
    return make_json_safe(result)
