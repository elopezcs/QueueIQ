from fastapi.testclient import TestClient
from app.main import create_app

client = TestClient(create_app())


def test_clinics_list():
    r = client.get("/clinics")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert {"id", "name", "address_or_city"} <= set(data[0].keys())


def test_clinic_status():
    clinics = client.get("/clinics").json()
    clinic_id = clinics[0]["id"]
    r = client.get(f"/clinics/{clinic_id}/status")
    assert r.status_code == 200
    s = r.json()
    assert {"queue_length", "servers_busy", "servers_total", "updated_at"} <= set(s.keys())
