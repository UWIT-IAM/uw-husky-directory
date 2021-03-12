from unittest import mock

import pytest
from bs4 import BeautifulSoup
from flask import Response
from flask.testing import FlaskClient
from uw_saml2.idp.uw import UwIdp
from werkzeug.local import LocalProxy


class TestSAMLBlueprint:
    @pytest.fixture(autouse=True)
    def initialize(self, injector, client: FlaskClient):
        self.mock_session = {}
        self.flask_client = client

        # Mock out the LocalProxy so that we can test its state
        # before and after SAML calls.
        orig_get = injector.get

        def _injector_get(cls):
            if cls is LocalProxy:
                return self.mock_session
            return orig_get(cls)

        with mock.patch.object(injector, "get") as mock_injector_get:
            mock_injector_get.side_effect = _injector_get
            yield

    def test_login(self):
        """Logs in to the mock IdP just to validate the flow."""
        assert not self.mock_session
        response: Response = self.flask_client.get("/")
        html = BeautifulSoup(response.data, "html.parser")
        assert html.find("a", dict(id="sign-in"))
        population_options = html.find_all("input", dict(name="population"))
        assert len(population_options) == 1
        response: Response = self.flask_client.get("/saml/login", follow_redirects=True)
        html = BeautifulSoup(response.data, "html.parser")
        assert response.status_code == 200
        assert "uwnetid" in self.mock_session
        assert not html.find("a", dict(id="sign-in"))
        population_options = html.find_all("input", dict(name="population"))
        assert len(population_options) == 3

    def test_logout(self):
        """Logs out after logging in to validate the flow."""
        self.test_login()
        response = self.flask_client.get("/saml/logout", follow_redirects=True)
        html = BeautifulSoup(response.data)
        assert html.find("a", dict(id="sign-in"))
        assert not self.mock_session

    def test_process_saml_request(self):
        """Since the mock flow doesn't use this method, we must verify it does what it's supposed to explicitly"""
        response = self.flask_client.post(
            "/saml/login",
            data={
                "idp": UwIdp.entity_id,
                "remote_user": "cooluser@washington.edu",
            },
            follow_redirects=True,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        assert self.mock_session.get("uwnetid") == "cooluser"
