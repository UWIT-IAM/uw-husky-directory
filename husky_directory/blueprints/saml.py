from urllib.parse import urljoin

import uw_saml2
from flask import Blueprint, Request, redirect
from injector import Module, inject, provider, singleton
from uw_saml2.idp import IdpConfig
from uw_saml2.idp.uw import UwIdp
from werkzeug.local import LocalProxy

from husky_directory.app_config import ApplicationConfig


class SAMLBlueprint(Blueprint):
    @inject
    def __init__(self, idp_config: IdpConfig, settings: ApplicationConfig):
        super().__init__("saml", __name__, url_prefix="/saml")
        self.idp_config = idp_config
        self.add_url_rule("/login", view_func=self.login, methods=["GET", "POST"])
        self.add_url_rule("/logout", view_func=self.login)
        self.app_settings = settings

    def login(self, request: Request, session: LocalProxy):
        session.clear()
        args = {
            "entity_id": self.app_settings.saml_entity_id,
            "acs_url": self.app_settings.saml_acs_url,
        }

        if request.method == "GET":
            args["return_to"] = request.args.get("return_to")
            return redirect(uw_saml2.login_redirect(**args))

        attributes = uw_saml2.process_response(request.form, **args)
        session["userid"] = attributes["uwnetid"]
        session["groups"] = attributes.get("groups", [])
        relay_state = request.form.get("RelayState")
        if relay_state and relay_state.startswith("/"):
            return redirect(urljoin(request.url_root, relay_state))

        return f'You have successfully logged in as {session["userid"]}'

    def logout(self, request: Request, session: LocalProxy):
        session.clear()
        return redirect("/")


class IdentityProviderModule(Module):
    @provider
    @singleton
    def provide_idp_config(self) -> IdpConfig:
        return UwIdp()
