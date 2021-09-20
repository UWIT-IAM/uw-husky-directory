import logging
import os
from datetime import datetime
from logging.config import dictConfig
from typing import List, NoReturn, Optional, Type, cast

import inflection
import pytz
from flask import Flask, session as flask_session
from flask_httpauth import HTTPBasicAuth
from flask_injector import FlaskInjector, request
from flask_session import RedisSessionInterface, Session
from injector import Injector, Module, provider, singleton
from jinja2.tests import test_undefined
from redis import Redis
from uw_saml2 import mock, python3_saml
from werkzeug.exceptions import HTTPException, InternalServerError
from werkzeug.local import LocalProxy

from husky_directory.blueprints.app import AppBlueprint
from husky_directory.blueprints.saml import (
    IdentityProviderModule,
    MockSAMLBlueprint,
    SAMLBlueprint,
)
from husky_directory.blueprints.search import SearchBlueprint
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.util import MetricsClient
from .app_config import (
    ApplicationConfig,
    ApplicationConfigInjectorModule,
    YAMLSettingsLoader,
)


def attach_app_error_handlers(app: Flask) -> NoReturn:
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
        IdentityProviderModule,
    ]


def create_app_injector() -> Injector:
    return Injector(modules=get_app_injector_modules())


class AppInjectorModule(Module):
    search_attributes = SearchDirectoryInput.search_methods()

    @provider
    @request
    def provide_request_session(self) -> LocalProxy:
        return cast(
            LocalProxy, flask_session
        )  # Cast this so that IDEs knows what's up; does not affect runtime

    @provider
    @singleton
    def provide_logger(
        self, yaml_loader: YAMLSettingsLoader, injector: Injector
    ) -> logging.Logger:
        logger_settings = yaml_loader.load_settings("logging")
        dictConfig(logger_settings)
        app_logger = logging.getLogger("gunicorn.error").getChild("app")
        formatter = app_logger.handlers[0].formatter
        formatter.injector = injector
        return app_logger

    def register_jinja_extensions(self, app: Flask):
        """You can define jinja filters here in order to make them available in our jinja templates."""

        @app.template_filter()
        def titleize(text):
            """
            Turns snake_case and camelCase into "Snake Case" and "Camel Case," respectively.
            Use: {{ some_string|titleize }}
            """
            return inflection.titleize(text)

        @app.template_filter()
        def singularize(text: str):
            """
            Takes something plural and makes it singular.
            Use: {{ "parrots"|singularize }}
            """
            return inflection.singularize(text)

        @app.template_filter()
        def linkify(text: str):
            """
            Replaces all non alphanum characters with '-' and lowercases
            everything.
                "foo: bar baz st. claire" => "foo-bar-baz-st-claire"
            use: {{ "Foo Bar Baz St. Claire"|linkify }}
            """
            return inflection.parameterize(text)

        @app.template_filter()
        def externalize(text):
            """
            Some values are great for api models but not so great for humans. So, this allows for that extra layer
            of translation where needed.

            If this gets more complicated for any reason, this table of internal vs. external values should be
            moved into its own service, or at least a dict.
            """
            if text == "employees":
                return "faculty/staff"
            return text

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

        @app.context_processor
        def provide_current_year():
            return {"current_year": datetime.utcnow().year}

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
        mock_saml_blueprint: MockSAMLBlueprint,
    ) -> Flask:
        # First we have to do some logging configuration, before the
        # app instance is created.

        # We've done our pre-work; now we can create the instance itself.
        app = Flask("husky_directory")
        app.jinja_env.trim_blocks = True
        app.jinja_env.lstrip_blocks = True
        app.config.update(app_settings.app_configuration)
        app.url_map.strict_slashes = (
            False  # Allows both '/search' and '/search/' to work
        )

        if app_settings.auth_settings.use_test_idp:
            python3_saml.MOCK = True
            mock.MOCK_LOGIN_URL = "/mock-saml/login"
            app.register_blueprint(mock_saml_blueprint)

        # App blueprints get registered here.
        app.register_blueprint(app_blueprint)
        app.register_blueprint(search_blueprint)
        app.register_blueprint(saml_blueprint)

        # Ensure the application is using the same logger as everything else.
        app.logger = logger

        # Bind an injector to the app itself to manage the scopes of
        # our dependencies appropriate for each request.
        FlaskInjector(app=app, injector=injector)
        self._configure_app_session(app, app_settings)
        self._configure_prometheus(app, app_settings, injector)
        attach_app_error_handlers(app)
        self.register_jinja_extensions(app)
        app.logger.info(
            f"Application worker started at "
            f'{datetime.utcnow().astimezone(pytz.timezone("US/Pacific"))}'
        )
        return app

    @staticmethod
    def _configure_prometheus(
        app: Flask, app_settings: ApplicationConfig, injector: Injector
    ):
        """
        Sets up a prometheus client with authorization and
        binds it to the Injector using the MetricsClient alias.
        :param app:
        :param app_settings:
        :param injector:
        :return:
        """
        secrets = app_settings.secrets
        metrics_auth = HTTPBasicAuth()

        @metrics_auth.verify_password
        def verify_credentials(username: str, password: str):
            if secrets.prometheus_username and secrets.prometheus_password:
                credentials = (
                    secrets.prometheus_username.get_secret_value(),
                    secrets.prometheus_password.get_secret_value(),
                )
                return (username, password) == credentials
            app.logger.warning(
                "No prometheus authorization is configured. Anyone can scrape these metrics."
            )
            return True  # If the environment isn't configured with auth (e.g., testing)

        metrics = MetricsClient(
            app,
            debug=True,
            metrics_decorator=metrics_auth.login_required,
            defaults_prefix=f"{app_settings.metrics_settings.metric_prefix}_flask",
        )
        app.metrics = metrics
        injector.binder.bind(MetricsClient, metrics, scope=singleton)

    @staticmethod
    def _configure_app_session(app: Flask, app_settings: ApplicationConfig) -> NoReturn:
        # There is something wrong with the flask_session implementation that
        # is supposed to translate flask config values into redis settings;
        # also, it doesn't support authorization (what?!) so we have to
        # use their model to explicitly set the interface instead of relying
        # on the magic.
        # TODO: It seems like flask_sessions is actually an abandoned project, so it might
        #       be better to just remove it and implement our own session
        #       interface based on their work. But this is fine for now.
        if app.config["SESSION_TYPE"] == "redis":
            redis_settings = app_settings.redis_settings
            app.logger.info(
                f"Setting up redis cache with settings: {redis_settings.flask_config_values}"
            )
            app.session_interface = RedisSessionInterface(
                redis=Redis(
                    host=redis_settings.host,
                    port=redis_settings.port,
                    username=redis_settings.namespace,
                    password=redis_settings.password.get_secret_value(),
                ),
                key_prefix=redis_settings.flask_config_values["SESSION_KEY_PREFIX"],
            )
        else:
            Session(app)


def create_app(injector: Optional[Injector] = None) -> Flask:
    injector = injector or create_app_injector()
    injector.binder.install(AppInjectorModule)
    return injector.get(Flask)


if __name__ == "__main__":  # pragma: no cover
    create_app().run(port=os.environ.get("FLASK_PORT", 8000))
