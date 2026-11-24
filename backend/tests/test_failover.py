"""
Tests for the X-Simulate-Failure hook and the 503 "all providers unavailable"
path. These mirror the exact example table in section 4 of the assignment.
"""


def test_failover_key1_fails_key2_answers(client):
    resp = client.post(
        "/chat",
        json={"session_id": "f1", "message": "failover test one"},
        headers={"X-Simulate-Failure": "key_1=429"},
    )
    assert resp.status_code == 200
    meta = resp.json()["metadata"]
    # key_1 was forced to fail, so key_2 answered after 1 failed attempt.
    assert meta["key_id"] == "key_2"
    assert meta["fallback_attempts"] == 1


def test_failover_with_500_status(client):
    resp = client.post(
        "/chat",
        json={"session_id": "f2", "message": "failover test two"},
        headers={"X-Simulate-Failure": "key_1=500"},
    )
    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "key_2"


def test_all_keys_fail_returns_503(client):
    resp = client.post(
        "/chat",
        json={"session_id": "f3", "message": "everything fails now"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 503
    assert resp.json() == {"detail": "all providers unavailable"}


def test_failed_request_is_not_added_to_history(client):
    # Force a total failure...
    client.post(
        "/chat",
        json={"session_id": "f4", "message": "doomed message"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    # ...the session should not exist in history at all (nothing was stored).
    resp = client.get("/sessions/f4/messages")
    assert resp.status_code == 404
