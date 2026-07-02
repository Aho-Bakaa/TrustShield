"""Deterministic test config: force rule-based LLM + no outbound network.

Set BEFORE importing the app so cached settings pick these up.
"""
import os
import sys
from pathlib import Path

os.environ["FORCE_MOCK_LLM"] = "true"
os.environ["NETWORK_ENABLED"] = "false"
os.environ["DB_PATH"] = ":memory:"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)
