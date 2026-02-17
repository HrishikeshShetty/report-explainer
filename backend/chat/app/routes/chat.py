from fastapi import APIRouter
from pydantic import BaseModel
from app.services.chat_engine import generate_chat_response

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    lipids: dict

@router.post("/ask")
def ask_question(payload: ChatRequest):
    answer = generate_chat_response(
        question=payload.question,
        lipids=payload.lipids
    )
    return {"answer": answer}