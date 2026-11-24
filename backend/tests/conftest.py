"""
conftest.py
-----------
Shared test setup. This runs BEFORE the app is imported, so we can point the
backend at a throwaway SQLite file and force MOCK mode (no real API keys needed).

An autouse fixture wipes the DB and the cache between every test, so tests never
leak state into each other.
"""

import os
import tempfile

import pytest

# --- configure the backend via env vars BEFORE importing the app -------------
_TMP_DB = os.path.join(tempfile.gettempdir(), "lyftr_test.db")

os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["MOCK_LLM"] = "true"                 # no real provider calls
os.environ["MOCK_LATENCY_MS"] = "20"            # keep the suite fast
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"
os.environ["CACHE_ENABLED"] = "true"
os.environ["LLM_API_KEYS"] = "test_key_1,test_key_2"   # two keys -> key_1, key_2
os.environ["LLM_MODEL"] = "gemini/gemini-2.0-flash"

from fastapi.testclient import TestClient  # noqa: E402  (import after env setup)

from app import cache, db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """A fresh TestClient for hitting the API in tests."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Before each test: empty the DB table and the in-memory cache."""
    db.init_db()
    db.clear_all()
    cache.clear()
    yield
