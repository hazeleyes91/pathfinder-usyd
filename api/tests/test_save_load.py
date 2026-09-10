import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_load_plan_no_cookie():
    """Verify loading without a session cookie returns null plan."""
    response = client.get("/api/plan/load")
    assert response.status_code == 200
    assert response.json() == {"plan": None}


def test_save_creates_session_and_cookie():
    """Verify autosaving without cookie creates new session and sets pathfinder_session cookie."""
    sample_plan = {
        "schemaVersion": 1,
        "metadata": {
            "title": "Computer Science Plan",
            "updatedAt": "2026-09-10T00:00:00.000Z",
        },
        "config": {"mode": "free", "maxYear": 3},
        "placements": [
            {"year": 1, "term": "sem1", "codes": ["INFO1110", "MATH1021"]},
            {"year": 1, "term": "sem2", "codes": ["COMP2123", "MATH1002"]},
        ],
    }

    response = client.post("/api/plan/autosave", json=sample_plan)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "session_id" in data
    assert len(data["session_id"]) > 0

    # Verify cookie attributes
    assert "pathfinder_session" in response.cookies
    session_cookie = response.cookies["pathfinder_session"]
    assert session_cookie == data["session_id"]


def test_save_and_load_roundtrip():
    """Verify saved plan is retrieved accurately via session cookie."""
    plan_payload = {
        "schemaVersion": 1,
        "metadata": {
            "title": "Engineering Double Major",
            "updatedAt": "2026-09-10T12:00:00.000Z",
        },
        "config": {"mode": "struct", "maxYear": 4},
        "placements": [
            {"year": 1, "term": "sem1", "codes": ["INFO1110", "MATH1021"]},
            {"year": 1, "term": "sem2", "codes": ["COMP2123", "ELEC1601"]},
            {"year": 2, "term": "sem1", "codes": ["COMP2017", "DATA2001"]},
        ],
    }

    save_resp = client.post("/api/plan/autosave", json=plan_payload)
    assert save_resp.status_code == 200
    session_id = save_resp.json()["session_id"]

    # Load with session cookie
    load_resp = client.get(
        "/api/plan/load", cookies={"pathfinder_session": session_id}
    )
    assert load_resp.status_code == 200
    loaded_body = load_resp.json()
    assert loaded_body["plan"] is not None

    plan = loaded_body["plan"]
    assert plan["schemaVersion"] == 1
    assert plan["metadata"]["title"] == "Engineering Double Major"
    assert plan["config"]["mode"] == "struct"
    assert plan["config"]["maxYear"] == 4
    assert len(plan["placements"]) == 3
    assert plan["placements"][2]["codes"] == ["COMP2017", "DATA2001"]


def test_save_updates_existing_session():
    """Verify saving with existing session cookie overwrites previous plan."""
    session_id = "test-session-save-load-update"
    v1_plan = {
        "schemaVersion": 1,
        "metadata": {"title": "Draft 1"},
        "config": {"mode": "free", "maxYear": 3},
        "placements": [{"year": 1, "term": "sem1", "codes": ["INFO1110"]}],
    }

    resp1 = client.post(
        "/api/plan/autosave",
        json=v1_plan,
        cookies={"pathfinder_session": session_id},
    )
    assert resp1.status_code == 200

    v2_plan = {
        "schemaVersion": 1,
        "metadata": {"title": "Draft 2 Final"},
        "config": {"mode": "struct", "maxYear": 3},
        "placements": [
            {"year": 1, "term": "sem1", "codes": ["INFO1110", "COMP2017"]}
        ],
    }

    resp2 = client.post(
        "/api/plan/autosave",
        json=v2_plan,
        cookies={"pathfinder_session": session_id},
    )
    assert resp2.status_code == 200

    load_resp = client.get(
        "/api/plan/load", cookies={"pathfinder_session": session_id}
    )
    assert load_resp.status_code == 200
    plan = load_resp.json()["plan"]
    assert plan["metadata"]["title"] == "Draft 2 Final"
    assert plan["config"]["mode"] == "struct"
    assert plan["placements"][0]["codes"] == ["INFO1110", "COMP2017"]


def test_session_isolation_and_unknown_cookie():
    """Verify unknown or missing sessions return plan: None."""
    resp = client.get(
        "/api/plan/load", cookies={"pathfinder_session": "non-existent-session-id"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"plan": None}
