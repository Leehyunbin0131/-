from __future__ import annotations


def test_api_flow(client) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ingest = client.post("/api/v1/ingestion/run", json={"rebuild_index": False})
    assert ingest.status_code == 200
    payload = ingest.json()
    assert payload["scanned_files"] == 1
    assert payload["ingested_files"] == 1
    assert payload["table_count"] == 2

    catalog = client.get("/api/v1/catalog/datasets")
    assert catalog.status_code == 200
    assert catalog.json()["count"] == 1

    start = client.post(
        "/api/v1/chat/session/start",
        json={
            "opening_question": "I want counseling using employment data in Seoul.",
            "user_profile": {
                "target_region": "Seoul"
            }
        },
    )
    assert start.status_code == 200
    body = start.json()
    assert body["stage"] == "intake"
    assert body["current_question"]["question_id"] == "current_stage"
    assert body["quota"]["trial_remaining"] == 5
    session_id = body["session_id"]

    answers = {
        "current_stage": "high_school",
        "goals": "employment outcomes in Seoul",
        "interests": ["software", "data"],
        "avoidances": ["long academic track"],
        "priorities": ["employment stability", "region"],
        "constraints": ["budget"],
        "decision_pain": "I do not know whether to optimize for interest or employment rate.",
    }

    while body["stage"] == "intake":
        question_id = body["current_question"]["question_id"]
        answer = answers.get(question_id, "Seoul")
        response = client.post(
            f"/api/v1/chat/session/{session_id}/answer",
            json={"answer": answer},
        )
        assert response.status_code == 200
        body = response.json()

    assert body["stage"] == "ready_for_summary"
    assert body["can_complete"] is True

    session_state = client.get(f"/api/v1/chat/session/{session_id}")
    assert session_state.status_code == 200
    assert session_state.json()["session"]["stage"] == "ready_for_summary"

    complete = client.post(f"/api/v1/chat/session/{session_id}/complete")
    assert complete.status_code == 200
    summary = complete.json()
    assert summary["summary"]["situation_summary"]
    assert summary["summary"]["recommended_directions"]
    assert summary["summary"]["risks_and_tradeoffs"]
    assert summary["trace_id"]
    assert summary["quota"]["trial_used"] == 1
    assert summary["quota"]["total_remaining"] == 4
    assert summary["stage"] == "active_counseling"

    for index in range(3):
        followup = client.post(
            f"/api/v1/chat/session/{session_id}/message",
            json={
                "question": f"Can you narrow this down further? #{index}",
                "client_request_id": f"followup-{index}",
            },
        )
        assert followup.status_code == 200
        payload = followup.json()
        assert payload["answer"]
        assert payload["stage"] == "active_counseling"

    last_free_turn = client.post(
        f"/api/v1/chat/session/{session_id}/message",
        json={
            "question": "One more follow-up please.",
            "client_request_id": "followup-last-free",
        },
    )
    assert last_free_turn.status_code == 200
    assert last_free_turn.json()["stage"] == "upgrade_required"
    assert last_free_turn.json()["quota"]["total_remaining"] == 0

    blocked = client.post(
        f"/api/v1/chat/session/{session_id}/message",
        json={
            "question": "This should require payment.",
            "client_request_id": "followup-blocked",
        },
    )
    assert blocked.status_code == 402


def test_guest_to_user_verification_flow(client) -> None:
    start = client.post("/api/v1/chat/session/start", json={})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    email_start = client.post(
        "/api/v1/auth/email/start",
        json={"email": "learner@example.com", "session_id": session_id},
    )
    assert email_start.status_code == 200
    verification_code = email_start.json()["verification_code"]
    assert verification_code

    verify = client.post(
        "/api/v1/auth/email/verify",
        json={
            "email": "learner@example.com",
            "code": verification_code,
            "session_id": session_id,
        },
    )
    assert verify.status_code == 200
    payload = verify.json()
    assert payload["actor_type"] == "user"
    assert payload["user"]["email"] == "learner@example.com"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["actor_type"] == "user"
