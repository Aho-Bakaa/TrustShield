"""Readable structured logging for the TrustShield pipeline.

Logs go to stdout so they appear inline in the uvicorn terminal. Every analysis
gets a short id so you can follow one request across stages:

  15:42:01 | INFO  | ts.api    | [a1b2c3] POST /analyze/text channel_hint=email len=182
  15:42:01 | INFO  | ts.fusion | [a1b2c3] channel=email entities=['SEBI'] links=1
  15:42:01 | INFO  | ts.fusion | [a1b2c3] triage=0.34 -> ESCALATE (reason: url present)
  15:42:02 | INFO  | ts.render | [a1b2c3] render http://... via playwright ok captures=True
  15:42:03 | INFO  | ts.llm    | [a1b2c3] groq/openai/gpt-oss-20b live 1455ms
  15:42:03 | INFO  | ts.fusion | [a1b2c3] VERDICT risk=100 high 'Phishing impersonation' 2100ms
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logger = logging.getLogger("ts")
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)-9s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ts.{name}")
