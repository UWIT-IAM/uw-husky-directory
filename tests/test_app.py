def test_get_index(client):
    assert client.get("/").status_code == 200


def test_get_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["ready"] is False


def test_get_ready(client):
    response = client.get("/health?ready")
    assert response.status_code == 200, response.data
    assert response.json["ready"] is True


def test_get_login(client, injector):
    response = client.get("/saml/login")
    assert response.status_code == 302, response.data


def test_get_logout(client, injector):
    response = client.get("/saml/logout")
    assert response.status_code == 302, response.data
