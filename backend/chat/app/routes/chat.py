from fastapi import APIRouter
from pydantic import BaseModel
from app.services.chat_engine import ChatEngine

router = APIRouter()
engine = ChatEngine()

class ChatRequest(BaseModel):
    question: str
    lipids: dict

@router.post("/ask")
def ask_question(payload: ChatRequest):
    answer = engine.answer(
        question=payload.question,
        lipids=payload.lipids
    )
    return {"answer": answer}