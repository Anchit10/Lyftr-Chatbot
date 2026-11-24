"""Tests for POST /chat: happy path, metadata shape, and validation (422)."""


def test_chat_basic_live_inference(client):
    resp = client.post("/chat", json={"session_id": "s-basic", "message": "Hello there"})
    assert resp.status_code == 200

    body = resp.json()
    assert body["session_id"] == "s-basic"
    assert isinstance(body["reply"], str) and len(body["reply"]) > 0

    meta = body["metadata"]
    # First time we see this message -> it must be a live call, not a cache hit.
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["model"] == "gemini/gemini-2.0-flash"
    assert meta["key_id"] == "key_1"            # first key answered
    assert meta["fallback_attempts"] == 0       # nothing failed before it
    assert isinstance(meta["latency_ms"], int)
    assert meta["input_tokens"] > 0
    assert meta["output_tokens"] > 0


def test_chat_rejects_empty_message(client):
    resp = client.post("/chat", json={"session_id": "s1", "message": "   "})
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_chat_rejects_too_long_message(client):
    resp = client.post("/chat", json={"session_id": "s1", "message": "x" * 4001})
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_chat_rejects_missing_session_id(client):
    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_system_prompt_is_accepted(client):
    resp = client.post(
        "/chat",
        json={
            "session_id": "s-sys",
            "message": "Who are you?",
            "system_prompt": "You are a pirate.",
        },
    )
    assert resp.status_code == 200
