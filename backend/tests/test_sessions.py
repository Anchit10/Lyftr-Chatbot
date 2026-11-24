"""
Tests for multi-turn memory and GET /sessions/{id}/messages.
"""


def test_history_is_stored_and_ordered(client):
    sid = "hist-1"
    client.post("/chat", json={"session_id": sid, "message": "first message"})
    client.post("/chat", json={"session_id": sid, "message": "second message"})

    resp = client.get(f"/sessions/{sid}/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == sid

    msgs = body["messages"]
    # Two turns => 4 rows: user, assistant, user, assistant (oldest first).
    assert len(msgs) == 4
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[0]["content"] == "first message"
    assert msgs[2]["content"] == "second message"

    # The system prompt must NOT appear in the stored history.
    assert all(m["role"] != "system" for m in msgs)

    # Assistant messages carry metadata; user messages don't.
    assert "metadata" in msgs[1]
    assert "metadata" not in msgs[0]


def test_unknown_session_returns_404(client):
    resp = client.get("/sessions/does-not-exist/messages")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "session not found"}


def test_sessions_stay_separate(client):
    client.post("/chat", json={"session_id": "sep-a", "message": "alpha"})
    client.post("/chat", json={"session_id": "sep-b", "message": "beta"})

    a = client.get("/sessions/sep-a/messages").json()["messages"]
    b = client.get("/sessions/sep-b/messages").json()["messages"]

    assert a[0]["content"] == "alpha"
    assert b[0]["content"] == "beta"
    # Session A never sees session B's message.
    assert all("beta" not in m["content"] for m in a)
