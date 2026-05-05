from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_categories_returns_list():
    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_categories_schema():
    response = client.get("/categories")
    for item in response.json():
        assert isinstance(item["id"], int)
        assert isinstance(item["name"], str)
        assert item["name"]
