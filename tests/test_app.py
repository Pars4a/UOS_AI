from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_homepage():
    response = client.get("/")
    assert response.status_code == 200

def test_homepage():
    response = client.get("/about")
    assert response.status_code == 200

def test_homepage():
    response = client.get("/contact")
    assert response.status_code == 200