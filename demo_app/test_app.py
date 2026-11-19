from fastapi.testclient import TestClient
from demo_app.app import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_calculate():
    res = client.get("/calculate?a=10&b=2")
    assert res.status_code == 200
    assert res.json()["result"] == 5.0
