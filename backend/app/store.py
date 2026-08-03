"""Minimal SQLite persistence for analyses (no external DB needed)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from .config import get_settings
from .schemas import AnalysisResult

_lock = Lock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = Path(get_settings().db_path)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                channel_type TEXT,
                risk_score INTEGER,
                risk_level TEXT,
                threat_label TEXT,
                created_at TEXT,
                payload TEXT
            )
            """
        )
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS share_tokens (
                token TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL,
                created_at TEXT,
                expires_at TEXT
            )
            """
        )
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_share_tokens_analysis ON share_tokens(analysis_id)")
        _conn.commit()
    return _conn


def save(result: AnalysisResult) -> None:
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO analyses VALUES (?,?,?,?,?,?,?)",
            (
                result.id,
                result.channel_type.value,
                result.risk_score,
                result.risk_level.value,
                result.threat_label,
                result.created_at,
                result.model_dump_json(),
            ),
        )
        conn.commit()


def get(analysis_id: str) -> AnalysisResult | None:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT payload FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    if not row:
        return None
    return AnalysisResult.model_validate(json.loads(row[0]))


def recent(limit: int = 25) -> list[dict]:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT id, channel_type, risk_score, risk_level, threat_label, created_at "
            "FROM analyses ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "channel_type": r[1],
            "risk_score": r[2],
            "risk_level": r[3],
            "threat_label": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


def create_share_token(analysis_id: str, ttl_days: int = 7) -> str:
    """Create a random share token for an analysis. Returns the token."""
    import secrets
    from datetime import datetime, timedelta, timezone

    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=ttl_days)
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO share_tokens VALUES (?,?,?,?)",
            (token, analysis_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    return token


def resolve_share_token(token: str) -> str | None:
    """Return the analysis_id if the token exists and is unexpired, else None."""
    from datetime import datetime, timezone

    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT analysis_id, expires_at FROM share_tokens WHERE token = ?", (token,)
        ).fetchone()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(row[1])
        if expires < datetime.now(timezone.utc):
            return None
    except ValueError:
        return None
    return row[0]
