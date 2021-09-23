import base64
from unittest import mock

import pytest
from pydantic import SecretStr

from husky_directory.app import create_app_injector
from husky_directory.app_config import ApplicationConfig
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.search import DirectorySearchService


def test_get_index(client, html_validator):
    response = client.get("/")
    assert response.status_code == 200
    with html_validator.validate_response(response) as html:
        assert "autofocus" in html.find("input", attrs={"name": "query"}).attrs


def test_create_injector():
    # This test is redundant but it keeps
    # coverage checker happy, because otherwise
    # this function is only called at the start
    # of a test session, before coverage checking
    # starts.
    assert create_app_injector()


def test_get_metrics(client):
    response = client.get("/metrics")
    assert response.status_code == 200


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
    else:
        app_config.version = None

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


def test_internal_server_error(client, injector, mock_injected):
    service = injector.get(DirectorySearchService)
    with mock_injected(DirectorySearchService, service):
        mock_search = mock.patch.object(service, "search_directory").start()
        mock_search.side_effect = RuntimeError
        response = client.post("/", data={"method": "boxNumber", "query": "123456"})
        assert response.status_code == 500


@pytest.mark.parametrize("auth_required", (True, False))
def test_prometheus_configuration(
    app_config: ApplicationConfig, client, auth_required: bool
):
    if auth_required:
        app_config.secrets.prometheus_username = SecretStr("username")
        app_config.secrets.prometheus_password = SecretStr("password")
        credentials = base64.b64encode("username:password".encode("UTF-8")).decode(
            "UTF-8"
        )
        response = client.get("/metrics")
        assert response.status_code == 401
        response = client.get(
            "/metrics", headers=dict(Authorization=f"Basic {credentials}")
        )
        assert response.status_code == 200
    else:
        assert client.get("/metrics").status_code == 200
