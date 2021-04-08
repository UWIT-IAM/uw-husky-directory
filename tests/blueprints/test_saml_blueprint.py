import pytest
from flask import Response
from flask.testing import FlaskClient
from uw_saml2.idp.uw import UwIdp
from werkzeug.local import LocalProxy


class TestSAMLBlueprint:
    @pytest.fixture(autouse=True)
    def initialize(self, injector, client: FlaskClient, html_validator, mock_injected):
        self.mock_session = {}
        self.flask_client = client
        self.html_validator = html_validator

        with mock_injected(LocalProxy, self.mock_session):
            yield

    def test_login(self):
        """Logs in to the mock IdP just to validate the flow."""
        assert not self.mock_session
        with self.html_validator.validate_response(self.flask_client.get("/")) as html:
            assert html.find("a", dict(id="sign-in"))
            population_options = html.find_all("input", dict(name="population"))
            assert len(population_options) == 1

        response: Response = self.flask_client.get("/saml/login", follow_redirects=True)
        assert response.status_code == 200
        assert "uwnetid" in self.mock_session

        with self.html_validator.validate_response(response) as html:
            assert not html.find("a", dict(id="sign-in"))
            population_options = html.find_all("input", dict(name="population"))
            assert len(population_options) == 3

    def test_logout(self):
        """Logs out after logging in to validate the flow."""
        self.test_login()
        response = self.flask_client.get("/saml/logout", follow_redirects=True)
        assert not self.mock_session
        with self.html_validator.validate_response(response) as html:
            assert html.find("a", dict(id="sign-in"))

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
