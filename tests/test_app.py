from unittest import mock

import pytest

from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.search import DirectorySearchService


def test_get_index(client, html_validator):
    response = client.get("/")
    assert response.status_code == 200
    with html_validator.validate_response(response) as html:
        assert "autofocus" in html.find("input", attrs={"name": "query"}).attrs


@pytest.mark.parametrize("pws_is_ready", (True, False))
@pytest.mark.parametrize("version", (None, "1.2.3"))
def test_get_health(client, pws_is_ready, version, app_config, injector, mock_injected):
    app_config.version = version
    should_be_ready = bool(pws_is_ready) and bool(version)
    pws_client = injector.get(PersonWebServiceClient)
    if not pws_is_ready:
        mock.patch.object(pws_client, "validate_connection", RuntimeError()).start()

    with mock_injected(PersonWebServiceClient, pws_client):
        response = client.get("/health")
        assert response.status_code == 200
        assert (
            response.json["ready"] == should_be_ready
        ), f"{response.json} {bool(pws_is_ready)} {bool(version)}"


@pytest.mark.parametrize("is_ready", (True, False))
def test_get_ready(client, app_config, is_ready: bool):
    if is_ready:
        app_config.version = "1.2.3"

    response = client.get("/health?ready")
    if is_ready:
        assert response.status_code == 200, response.data
        assert response.json["ready"] is True, response.json
    else:
        assert response.status_code == 500
        assert "ready=False" in response.data.decode("UTF-8"), response.data


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
