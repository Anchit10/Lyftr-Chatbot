"""
cache.py
--------
A tiny in-memory response cache (a Python dict).

The assignment allows LiteLLM's "in-memory or disk" cache. We keep an explicit
in-memory cache here instead so the behaviour is 100% predictable and matches the
contract exactly:

  * The cache KEY is the model name + the full message list sent to the LLM
    (system prompt + history + new message). So the same first message in a
    brand-new session returns a cache hit the second time, but a different
    message never does.
  * A cache hit returns the identical reply text AND the token counts that were
    stored with the original live response (tokens are "per request", not a
    running total).

Note: because this is in-memory, the cache resets when the process restarts.
That is fine and allowed ("in-memory").
"""

import hashlib
import json

# The actual store: cache_key -> {"reply", "input_tokens", "output_tokens"}
_store: dict[str, dict] = {}


def make_key(model: str, messages: list[dict]) -> str:
    """
    Build a stable cache key from the model + the exact messages.
    We hash the JSON so the key is short and order-sensitive.
    """
    blob = json.dumps({"model": model, "messages": messages}, sort_keys=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get(key: str) -> dict | None:
    """Return the cached entry for this key, or None on a miss."""
    return _store.get(key)


def set(key: str, reply: str, input_tokens: int, output_tokens: int) -> None:
    """Store a fresh live response so future identical requests are cache hits."""
    _store[key] = {
        "reply": reply,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def clear() -> None:
    """Empty the cache. Used by the test suite between tests."""
    _store.clear()
