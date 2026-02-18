from __future__ import annotations

import json
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.chat_engine import ChatEngine
from app.db import get_conn

router = APIRouter()
engine = ChatEngine()


class AskRequest(BaseModel):
    question: str
    lipids: Optional[Dict[str, Any]] = None
    report_id: Optional[str] = None

    # optional: later we can use this from frontend localStorage/cookie
    user_id: Optional[str] = None


@router.post("/ask")
def ask(req: AskRequest):
    # your current chat logic
    result = engine.answer(req.question, req.lipids or {})

    # persist to sqlite
    user_id = (req.user_id or "default").strip() or "default"

    sources_json = json.dumps(result.get("sources", []), ensure_ascii=False)
    highlights_json = json.dumps(result.get("highlights", []), ensure_ascii=False)

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO chat_messages (user_id, question, answer, mode, sources_json, highlights_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                req.question,
                result.get("answer", ""),
                result.get("mode"),
                sources_json,
                highlights_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return result


@router.get("/history")
def history(
    limit: int = Query(20, ge=1, le=200),
    user_id: str = Query("default"),
):
    """
    Returns last N messages for the given user_id.
    Frontend can call: /api/chat/history?limit=20&user_id=default
    """
    uid = (user_id or "default").strip() or "default"

    conn = get_conn()
    try:
        # newest first
        rows = conn.execute(
            """
            SELECT id, user_id, question, answer, mode, sources_json, highlights_json, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (uid, limit),
        ).fetchall()
    finally:
        conn.close()

    items: List[Dict[str, Any]] = []
    for r in rows:
        # sqlite row may be tuple or Row; handle both
        if isinstance(r, dict):
            row = r
        else:
            # expected order based on SELECT
            row = {
                "id": r[0],
                "user_id": r[1],
                "question": r[2],
                "answer": r[3],
                "mode": r[4],
                "sources_json": r[5],
                "highlights_json": r[6],
                "created_at": r[7],
            }

        # decode json fields safely
        try:
            sources = json.loads(row.get("sources_json") or "[]")
        except Exception:
            sources = []
        try:
            highlights = json.loads(row.get("highlights_json") or "[]")
        except Exception:
            highlights = []

        items.append(
            {
                "id": row.get("id"),
                "question": row.get("question") or "",
                "answer": row.get("answer") or "",
                "mode": row.get("mode") or "",
                "sources": sources,
                "highlights": highlights,
                "created_at": row.get("created_at"),
            }
        )

    # return oldest -> newest for nicer UI display
    items.reverse()

    return {"items": items, "count": len(items), "user_id": uid}
