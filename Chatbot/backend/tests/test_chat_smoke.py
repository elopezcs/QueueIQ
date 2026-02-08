from fastapi.testclient import TestClient
from app.main import create_app

client = TestClient(create_app())


def test_chat_smoke_flow():
    clinics = client.get("/clinics").json()
    clinic_id = clinics[0]["id"]

    start = client.post("/chat/start", json={"clinic_id": clinic_id})
    assert start.status_code == 200
    s = start.json()
    session_id = s["session_id"]
    assert session_id

    turn = client.post(
        "/chat/turn",
        json={"session_id": session_id, "user_message": "I have a cough and sore throat."},
    )
    assert turn.status_code == 200
    t = turn.json()
    assert "assistant_message" in t
    assert "progress" in t

    end = client.post("/chat/end", json={"session_id": session_id})
    assert end.status_code == 200
    out = end.json()
    assert out["session_id"] == session_id
    assert out["urgency_band"] in ["low", "medium", "high"]
    assert isinstance(out["wait_p50_minutes"], int)
    assert isinstance(out["wait_p90_minutes"], int)
