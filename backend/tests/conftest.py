"""Deterministic test config: no network, no LLM — never live API calls."""
import os
import sys
from pathlib import Path

os.environ["TS_TEST"] = "1"
os.environ["NETWORK_ENABLED"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.config import Settings

_settings = Settings(
    _env_file=None,
    groq_api_key="",
    openrouter_api_key="",
    gemini_api_key="",
    network_enabled=False,
    db_path=":memory:",
    render_enabled=False,
)

import app.config as _cfg
_cfg.get_settings = lambda: _settings


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
