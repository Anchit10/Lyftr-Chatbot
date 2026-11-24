"""
config.py
---------
Reads every setting from environment variables (the assignment requires
"all configuration through environment variables").

Nothing here is hard-coded except sensible defaults, so the same code runs
locally, in Docker, and in the cloud just by changing env vars.
"""

import os


def _as_bool(value: str) -> bool:
    """Turn strings like 'true', '1', 'yes' into a real boolean."""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str) -> list[str]:
    """Turn 'a, b ,c' into ['a', 'b', 'c'], dropping blanks."""
    return [item.strip() for item in value.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# API keys / model
# ---------------------------------------------------------------------------
# LLM_API_KEYS is a comma-separated pool, e.g. "sk-aaa,sk-bbb".
# The FIRST key becomes "key_1", the second "key_2", and so on (the order
# matters because failover walks the pool top to bottom).
_raw_keys = _split_csv(os.getenv("LLM_API_KEYS", "key_1_placeholder,key_2_placeholder"))

# KEY_POOL is a list of (key_id, key_value) tuples: [("key_1", "sk-aaa"), ...]
KEY_POOL: list[tuple[str, str]] = [
    (f"key_{i + 1}", key) for i, key in enumerate(_raw_keys)
]

# The model LiteLLM should call. Default is Google Gemini's free flash model.
# (LiteLLM uses the "provider/model" naming convention.)
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# e.g. "sqlite:////data/app.db"  -> absolute path /data/app.db
#      "sqlite:///./app.db"      -> relative path ./app.db
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:////data/app.db")

# ---------------------------------------------------------------------------
# CORS: which frontend origins are allowed to call this backend.
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS: list[str] = _split_csv(
    os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
)

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
# Must be true on the deployed backend for the X-Simulate-Failure header to work.
ENABLE_FAILURE_SIMULATION: bool = _as_bool(os.getenv("ENABLE_FAILURE_SIMULATION", "true"))

# Turn the response cache on/off. Reported by GET /health as "cache_enabled".
CACHE_ENABLED: bool = _as_bool(os.getenv("CACHE_ENABLED", "true"))

# MOCK_LLM=true makes the backend return a fake (but realistic) reply instead of
# calling a real provider. This lets the whole stack run and the tests pass with
# NO real API keys. Flip to false once you add real keys.
MOCK_LLM: bool = _as_bool(os.getenv("MOCK_LLM", "true"))

# Fake latency (milliseconds) added to a MOCK live call so a cache hit is
# visibly faster than a live call during the demo. Ignored when MOCK_LLM=false.
MOCK_LATENCY_MS: int = int(os.getenv("MOCK_LATENCY_MS", "200"))

# The system prompt used when the client doesn't send its own.
DEFAULT_SYSTEM_PROMPT: str = os.getenv(
    "DEFAULT_SYSTEM_PROMPT", "You are a helpful assistant."
)
