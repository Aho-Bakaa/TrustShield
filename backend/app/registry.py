"""Loads the official-source allowlist / entity registry (cached)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).parent / "data" / "allowlist.json"


@lru_cache
def registry() -> dict[str, Any]:
    with _DATA.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def official_domains() -> dict[str, dict[str, Any]]:
    """registered-domain -> metadata."""
    return {d["domain"].lower(): d for d in registry().get("official_domains", [])}


@lru_cache
def known_entities() -> list[dict[str, Any]]:
    return registry().get("entities", [])
