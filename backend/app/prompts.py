from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache
def load(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()
