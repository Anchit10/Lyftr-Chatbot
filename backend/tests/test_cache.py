"""
Tests for response caching.

The cache key is model + full message list. So the SAME first message in two
different-but-fresh sessions produces the same message list (system prompt +
that one user message) and must be served from cache the second time.
"""


def test_second_identical_first_message_is_cache_hit(client):
    payload_a = {"session_id": "cache-a", "message": "What is the capital of France?"}
    payload_b = {"session_id": "cache-b", "message": "What is the capital of France?"}

    first = client.post("/chat", json=payload_a).json()
    second = client.post("/chat", json=payload_b).json()

    # First call = live, second (identical first message) = cache hit.
    assert first["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert second["metadata"]["resolution_source"] == "LLM_CACHE"

    # A cache hit returns the identical reply text...
    assert second["reply"] == first["reply"]
    # ...the stored tokens (same numbers)...
    assert second["metadata"]["input_tokens"] == first["metadata"]["input_tokens"]
    assert second["metadata"]["output_tokens"] == first["metadata"]["output_tokens"]
    # ...a null key_id and zero fallback attempts...
    assert second["metadata"]["key_id"] is None
    assert second["metadata"]["fallback_attempts"] == 0
    # ...and must be faster than the live call.
    assert second["metadata"]["latency_ms"] <= first["metadata"]["latency_ms"]


def test_different_message_is_not_cache_hit(client):
    client.post("/chat", json={"session_id": "c1", "message": "First question"})
    other = client.post(
        "/chat", json={"session_id": "c2", "message": "A totally different question"}
    ).json()
    assert other["metadata"]["resolution_source"] == "LIVE_INFERENCE"
