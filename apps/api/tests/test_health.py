from fastapi.testclient import TestClient

from moneyball.api.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_db_ok():
    resp = client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json()["database"] == "reachable"
