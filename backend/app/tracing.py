"""Langfuse observability — traces every LLM call + verdict for scoring improvement.

When credentials are set (LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY), every
analysis run creates a trace with:
  - Step 1: intake (channel, entities, links)
  - Step 2: detector (probability, llm used, render used)
  - Step 3: verdict (risk score, level, threat label, confidence)
  - Metadata: analysis_id, recommended action, evidence count

When credentials are empty, this is a no-op — no overhead, no errors.
"""
from __future__ import annotations

import contextvars
import logging
from datetime import datetime, timezone
from typing import Any

from .config import get_settings

_log = logging.getLogger("ts.langfuse")

_langfuse: Any = None
_langfuse_checked = False

_active_trace = contextvars.ContextVar("ts_langfuse_trace", default=None)
_active_run_id = contextvars.ContextVar("ts_langfuse_run_id", default=None)


def _ensure_client():
    global _langfuse, _langfuse_checked
    if _langfuse_checked:
        return _langfuse
    _langfuse_checked = True
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_host,
        )
        _log.info("langfuse connected to %s", s.langfuse_host)
    except Exception as exc:
        _log.warning("langfuse init failed: %s", str(exc)[:120])
        _langfuse = None
    return _langfuse


def trace_start(name: str, metadata: dict[str, Any] | None = None) -> Any | None:
    client = _ensure_client()
    if not client:
        return None
    try:
        from langfuse import create_trace_id
        trace_id = create_trace_id()
        trace = client.trace(
            id=trace_id,
            name=name,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
        _active_trace.set(trace)
        _active_run_id.set(trace_id)
        return trace
    except Exception as exc:
        _log.debug("langfuse trace start failed: %s", str(exc)[:100])
        return None


def trace_step(name: str, input_data: dict | None = None,
               output_data: dict | None = None,
               metadata: dict | None = None) -> Any | None:
    client = _ensure_client()
    if not client:
        return None
    trace = _active_trace.get()
    if not trace:
        return None
    try:
        return trace.span(
            name=name,
            input=input_data,
            output=output_data,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as exc:
        _log.debug("langfuse span failed: %s", str(exc)[:100])
        return None


def trace_generation(name: str, model: str, prompt: str,
                     completion: str, usage: dict | None = None,
                     metadata: dict | None = None) -> Any | None:
    """Record an LLM call (prompt → completion) for score tracking over time."""
    client = _ensure_client()
    if not client:
        return None
    trace = _active_trace.get()
    if not trace:
        return None
    try:
        return trace.generation(
            name=name,
            model=model,
            input=prompt[:4000],
            output=completion[:2000],
            usage=usage,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as exc:
        _log.debug("langfuse generation failed: %s", str(exc)[:100])
        return None


def trace_flush():
    client = _ensure_client()
    if not client:
        return
    try:
        client.flush()
    except Exception as exc:
        _log.debug("langfuse flush failed: %s", str(exc)[:100])
