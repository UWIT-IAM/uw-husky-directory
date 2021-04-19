import getpass
from logging import Logger

import uw_saml2
from flask import Blueprint, Request, redirect
from injector import Module, inject, provider, singleton
from uw_saml2.idp import IdpConfig
from uw_saml2.idp.uw import UwIdp
from werkzeug.local import LocalProxy

from husky_directory.app_config import ApplicationConfig


class SAMLBlueprint(Blueprint):
    @inject
    def __init__(
        self, idp_config: IdpConfig, settings: ApplicationConfig, logger: Logger
    ):
        super().__init__("saml", __name__, url_prefix="/saml")
        self.idp_config = idp_config
        self.add_url_rule("/login", view_func=self.login, methods=["GET", "POST"])
        self.add_url_rule("/logout", view_func=self.logout)
        self.auth_settings = settings.auth_settings
        self.logger = logger

    def process_saml_request(self, request: Request, session: LocalProxy, **kwargs):
        self.logger.info(f"Processing SAML POST request from {request.remote_addr}")
        attributes = uw_saml2.process_response(request.form, **kwargs)
        session["uwnetid"] = attributes["uwnetid"]
        self.logger.info(f"Signed in user {session['uwnetid']}")
        relay_state = request.form.get("RelayState")
        return redirect(relay_state or "/")

    def login(self, request: Request, session: LocalProxy):
        session.clear()
        args = {
            "entity_id": self.auth_settings.saml_entity_id,
            "acs_url": self.auth_settings.saml_acs_url,
        }

        if request.method == "GET":
            self.logger.info(f"Redirecting {request.remote_addr} to SAML sign in.")
            return redirect(uw_saml2.login_redirect(**args))

        return self.process_saml_request(request, session, **args)

    def logout(self, request: Request, session: LocalProxy):
        session.clear()
        return redirect("/")


class MockSAMLBlueprint(Blueprint):
    @inject
    def __init__(self):
        super().__init__("mock-saml", __name__, url_prefix="/mock-saml")
        self.add_url_rule(
            "/login", view_func=self.process_saml_request, methods=["GET"]
        )

    def process_saml_request(self, request: Request, session: LocalProxy):
        session["uwnetid"] = getpass.getuser()
        return redirect("/")


class IdentityProviderModule(Module):
    @provider
    @singleton
    def provide_idp_config(self) -> IdpConfig:
        return UwIdp()
