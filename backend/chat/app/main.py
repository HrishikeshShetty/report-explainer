from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.chat import router as chat_router
from app.db import init_db  # ✅ add

app = FastAPI(title="Report Explainer Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    init_db()  # ✅ ensure table exists

app.include_router(chat_router, prefix="/api/chat")

@app.get("/")
def root():
    return {"message": "Chat service is running"}
