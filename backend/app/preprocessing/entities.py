"""Named-entity extraction for securities-market actors.

Lightweight keyword/alias matcher over the known-entity registry — no heavy NER
model needed for the MVP, and it keeps the demo deterministic.
"""
from __future__ import annotations

import re

from ..registry import known_entities
from ..schemas import Entity


def extract_entities(text: str) -> list[Entity]:
    if not text:
        return []
    found: dict[str, Entity] = {}
    for row in known_entities():
        names = [row["text"], *row.get("aliases", [])]
        for name in names:
            if re.search(rf"\b{re.escape(name)}\b", text, re.I):
                key = row["text"]
                if key not in found:
                    found[key] = Entity(
                        text=row["text"],
                        type=row["type"],
                        criticality=float(row.get("criticality", 0.5)),
                    )
                break
    return sorted(found.values(), key=lambda e: e.criticality, reverse=True)


def max_criticality(entities: list[Entity]) -> float:
    return max((e.criticality for e in entities), default=0.0)
