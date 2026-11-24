"""
Tests focused specifically on API-key RATE LIMITING (HTTP 429).

Rate limiting is the main reason the assignment wants a key pool: when a provider
says "429 Too Many Requests", the gateway must transparently fall over to the
next key so the user never sees a broken screen. These tests force 429s with the
X-Simulate-Failure hook and assert the gateway handles them correctly.
"""


def test_rate_limited_key_falls_over_to_next_key(client):
    # key_1 is rate limited (429) -> key_2 must answer, with 1 recorded failure.
    resp = client.post(
        "/chat",
        json={"session_id": "rl1", "message": "rate limit failover please"},
        headers={"X-Simulate-Failure": "key_1=429"},
    )
    assert resp.status_code == 200
    meta = resp.json()["metadata"]
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["key_id"] == "key_2"
    assert meta["fallback_attempts"] == 1


def test_all_keys_rate_limited_returns_503(client):
    # Every key is rate limited -> clean 503, no crash, nothing stored.
    resp = client.post(
        "/chat",
        json={"session_id": "rl2", "message": "all keys rate limited"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 503
    assert resp.json() == {"detail": "all providers unavailable"}
    # The failed request must NOT be written to history.
    assert client.get("/sessions/rl2/messages").status_code == 404


def test_cache_shields_a_rate_limited_provider(client):
    """
    After a rate-limited failover produces an answer, the SAME request should be
    served from cache next time — so a repeat never hits the rate-limited
    provider again.
    """
    msg = {"session_id": "rl3", "message": "cache beats the rate limit"}

    # 1st call: key_1 is rate limited, key_2 answers live, result gets cached.
    first = client.post(
        "/chat", json=msg, headers={"X-Simulate-Failure": "key_1=429"}
    ).json()
    assert first["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert first["metadata"]["key_id"] == "key_2"

    # 2nd identical call (in a fresh session so the message list matches): even
    # with BOTH keys rate limited, the cache answers -> no provider is touched.
    second = client.post(
        "/chat",
        json={"session_id": "rl4", "message": "cache beats the rate limit"},
        headers={"X-Simulate-Failure": "*=429"},
    ).json()
    assert second["metadata"]["resolution_source"] == "LLM_CACHE"
    assert second["metadata"]["key_id"] is None
    assert second["metadata"]["fallback_attempts"] == 0
    assert second["reply"] == first["reply"]
