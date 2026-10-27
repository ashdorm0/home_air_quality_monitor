from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_endpoint():

    response = client.get("/")

    assert response.status_code == 200

    assert response.json() == {
    "message": "Home Air Quality Monitor API",
    "version": "0.2.0"
    }


def test_health_endpoint():

    response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "healthy",
        "database": "connected"
    }