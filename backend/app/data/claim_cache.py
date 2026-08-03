"""Claim verification cache (roadmap 2.3).

Common claims like "SEBI bans retail investors" are re-checked on every query,
which burns rate limits and adds latency. This module caches the result of a
web-search verification keyed by a normalized hash of the claim, with a TTL.

Design: same SQLite file as analyses (db_path), separate table. Standalone
connection + lock so it never blocks the analyses connection.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from threading import Lock

from ..config import get_settings

_lock = Lock()
_conn: sqlite3.Connection | None = None

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days

_NORMALIZE = re.compile(r"[^a-z0-9]+")


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = Path(get_settings().db_path)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS claim_cache (
                claim_hash TEXT PRIMARY KEY,
                query TEXT,
                payload TEXT,
                cached_at REAL,
                expires_at REAL
            )
            """
        )
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_claim_cache_expires ON claim_cache(expires_at)")
        _conn.commit()
    return _conn


def _hash(query: str) -> str:
    norm = _NORMALIZE.sub(" ", (query or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]


def get_cached(query: str) -> dict | None:
    """Return cached verification result if fresh, else None."""
    if not query or not query.strip():
        return None
    now = time.time()
    try:
        with _lock:
            conn = _connect()
            row = conn.execute(
                "SELECT payload FROM claim_cache WHERE claim_hash = ? AND expires_at > ?",
                (_hash(query), now),
            ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def set_cached(query: str, payload: dict, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Store a verification result for a claim."""
    if not query or not query.strip() or not payload:
        return
    now = time.time()
    try:
        with _lock:
            conn = _connect()
            conn.execute(
                "INSERT OR REPLACE INTO claim_cache VALUES (?,?,?,?,?)",
                (_hash(query), query[:500], json.dumps(payload, default=str),
                 now, now + ttl_seconds),
            )
            conn.commit()
    except Exception:
        pass


def clear_expired() -> int:
    """Delete expired rows. Returns count removed."""
    try:
        with _lock:
            conn = _connect()
            cur = conn.execute("DELETE FROM claim_cache WHERE expires_at <= ?", (time.time(),))
            conn.commit()
            return cur.rowcount
    except Exception:
        return 0
