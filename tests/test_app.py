def test_get_index(client):
    assert client.get("/").status_code == 200


def test_get_health(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json["ready"] is False


def test_get_ready(client):
    response = client.get("/healthz?ready")
    assert response.status_code == 200
    assert response.json["ready"] is True
