from unittest import mock

from husky_directory.services.search import DirectorySearchService


def test_get_index(client, html_validator):
    response = client.get("/")
    assert response.status_code == 200
    with html_validator.validate_response(response) as html:
        assert "autofocus" in html.find("input", attrs={"name": "query"}).attrs


def test_get_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["ready"] is False


def test_get_ready(client):
    response = client.get("/health?ready")
    assert response.status_code == 200, response.data
    assert response.json["ready"] is True


def test_get_login(client):
    response = client.get("/saml/login")
    assert response.status_code == 302, response.data


def test_get_logout(client):
    response = client.get("/saml/logout")
    assert response.status_code == 302, response.data


def test_bad_request_error(client):
    response = client.get("/search?boxNumber=ABCDEFG")
    assert response.status_code == 400


def test_internal_server_error(client, injector, mock_injected):
    service = injector.get(DirectorySearchService)
    with mock_injected(DirectorySearchService, service):
        mock_search = mock.patch.object(service, "search_directory").start()
        mock_search.side_effect = RuntimeError
        response = client.get("/search?boxNumber=123456")
        assert response.status_code == 500
