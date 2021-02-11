import logging
from logging.config import dictConfig
from typing import List, NoReturn, Optional, Type

from flask import Flask, session
from flask_injector import FlaskInjector, request
from inflection import titleize as titleize_
from injector import Injector, Module, provider, singleton
from jinja2.tests import test_undefined
from pydantic import ValidationError
from uw_saml2 import mock, python3_saml
from werkzeug.exceptions import BadRequest, HTTPException, InternalServerError
from werkzeug.local import LocalProxy

from husky_directory.blueprints.app import AppBlueprint
from husky_directory.blueprints.saml import IdentityProviderModule, SAMLBlueprint
from husky_directory.blueprints.search import SearchBlueprint
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.util import UtilityInjectorModule
from .app_config import (
    ApplicationConfig,
    ApplicationConfigInjectorModule,
    YAMLSettingsLoader,
)


def attach_app_error_handlers(app: Flask) -> NoReturn:
    @app.errorhandler(ValidationError)
    def handle_validation_errors(e: ValidationError):
        return BadRequest(str(e))

    @app.errorhandler(Exception)
    def log_all_errors(e: Exception):
        if isinstance(e, HTTPException):
            app.logger.info(str(e))
            return e
        app.logger.exception(e)
        return InternalServerError(str(e), original_exception=e)


def get_app_injector_modules() -> List[Type[Module]]:
    return [
        ApplicationConfigInjectorModule,
        UtilityInjectorModule,
        IdentityProviderModule,
    ]


def create_app_injector() -> Injector:
    return Injector(modules=get_app_injector_modules())


class AppInjectorModule(Module):
    search_attributes = list(SearchDirectoryInput.__fields__.keys())

    @provider
    @request
    def provide_request_session(self) -> LocalProxy:
        return session  # Ignore IDE errors here. I hunted this down and determined the IDE is just confused.

    @provider
    @singleton
    def provide_logger(self, yaml_loader: YAMLSettingsLoader) -> logging.Logger:
        logger_settings = yaml_loader.load_settings("logging")
        dictConfig(logger_settings)
        gunicorn_error_logger = logging.getLogger("gunicorn.error")
        return gunicorn_error_logger

    def register_jinja_extensions(self, app: Flask):
        """You can define jinja filters here in order to make them available in our jinja templates."""

        @app.template_filter()
        def titleize(text):
            """
            Turns snake_case and camelCase into "Snake Case" and "Camel Case," respectively.
            Use: {{ some_string|titleize }}
            """
            return titleize_(text)

        @app.template_test()
        def blank(val):
            """
            A quick way to test whether a value is undefined OR none.
            This is an alternative to writing '{% if val is defined and val is not sameas None %}'
            """
            return test_undefined(val) or val is None

        @app.context_processor
        def provide_search_attributes():
            """Makes the list of search attributes available to the parser without having to hard-code them."""
            return {"search_attributes": self.search_attributes}

    @provider
    @singleton
    def provide_app(
        self,
        injector: Injector,
        app_settings: ApplicationConfig,
        logger: logging.Logger,
        # Any blueprints that are depended on here must
        # get registered below, under "App blueprints get registered here."
        search_blueprint: SearchBlueprint,
        app_blueprint: AppBlueprint,
        saml_blueprint: SAMLBlueprint,
    ) -> Flask:
        # First we have to do some logging configuration, before the
        # app instance is created.

        if app_settings.use_test_idp:
            python3_saml.MOCK = True
            mock.MOCK_LOGIN_URL = "/"

        # We've done our pre-work; now we can create the instance itself.
        app = Flask("husky_directory")
        app.secret_key = app_settings.cookie_secret_key
        app.url_map.strict_slashes = (
            False  # Allows both '/search' and '/search/' to work
        )

        # App blueprints get registered here.
        app.register_blueprint(app_blueprint)
        app.register_blueprint(search_blueprint)
        app.register_blueprint(saml_blueprint)

        # Ensure the application is using the same logger as everything else.
        app.logger.handlers = logger.handlers

        # Bind an injector to the app itself to manage the scopes of
        # our dependencies appropriate for each request.
        FlaskInjector(app=app, injector=injector)
        attach_app_error_handlers(app)
        self.register_jinja_extensions(app)
        return app


def create_app(injector: Optional[Injector] = None) -> Flask:
    injector = injector or create_app_injector()
    injector.binder.install(AppInjectorModule)
    return injector.get(Flask)


if __name__ == "__main__":  # pragma: no cover
    create_app().run()
