from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


def _find_repo_root(start: Path) -> Path:
    # same idea as your chat_engine: locate repo root reliably
    for p in [start] + list(start.parents):
        if (p / "README.md").exists() and (p / "backend").exists():
            return p
    return start.parents[5]


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
DB_PATH = Path(os.getenv("CHAT_DB_PATH", str(REPO_ROOT / "backend" / "chat" / "data" / "chat_history.sqlite3")))


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              question TEXT NOT NULL,
              answer TEXT NOT NULL,
              mode TEXT,
              sources_json TEXT,
              highlights_json TEXT
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_messages(user_id, created_at);")
        conn.commit()
    finally:
        conn.close()
