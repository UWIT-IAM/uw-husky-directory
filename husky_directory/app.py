from __future__ import annotations

import functools
import logging
from abc import ABC
from logging.config import dictConfig
from typing import NoReturn, Optional, Type

from flask import Flask, Request, jsonify, render_template
from flask.blueprints import Blueprint
from flask.views import View
from flask_injector import FlaskInjector, RequestScope
from injector import Injector, inject, singleton
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest, HTTPException, InternalServerError

from husky_directory.util import UtilityInjectorModule
from .app_config import ApplicationConfigInjectorModule, YAMLSettingsLoader
from .models.search import DirectoryBaseModel, SearchDirectoryInput
from .services.search import DirectorySearchService

app_module = Blueprint("main", "app")


class DirectoryView(View, ABC):
    """
    A base class that wires up the necessary injected dependencies for views that descent from it.
    Descendants must implement the 'dispatch_request' method.
    See flask documentation here: https://flask.palletsprojects.com/en/1.1.x/views

    """

    @inject
    def __init__(
        self,
        injector: Injector,
        request: Request,
        directory: DirectorySearchService,
        logger: logging.Logger,
    ):
        self.logger = logger
        self.injector = injector
        self.request = request
        self.directory = directory


@app_module.route("/")
def index(request: Request, logger: logging.Logger):
    logger.info(f"Someone is here: {request}")
    return render_template("index.html")


def inject_request_input(input_model: Type[DirectoryBaseModel]):
    """
    A decorator for DirectoryView methods that automatically parse query params into
    some given model. The model object becomes a request-scoped parameter that can then be
    retrieved from the injector.

    Raises a BadRequest error if the input cannot be parsed to the given model.

    Usage:

        class SomeModel:
            bar: str


        class Foo(DirectoryView):
            @inject_request_input(SomeModel)
            def dispatch_request(self):
                obj = self.injector.get(SomeModel)

                # Assuming a request url like: /foo?bar=hello
                assert obj.bar == 'hello'  # True
    """

    def wrapper(method):
        @functools.wraps(method)
        def inner(instance: Search, *args, **kwargs):
            injector = instance.injector
            logger = injector.get(logging.Logger)
            request: Request = injector.get(Request)
            try:
                request_input = input_model.parse_obj(request.args)
            except ValidationError as e:
                raise BadRequest(
                    f"Could not parse request to {input_model.__name__}: {str(e)}"
                )
            injector.binder.bind(input_model, request_input, scope=RequestScope)
            logger.info(f"Bound {request_input} to {input_model.__name__}")
            return method(instance, *args, **kwargs)

        return inner

    return wrapper


class Search(DirectoryView):
    @inject_request_input(SearchDirectoryInput)
    def dispatch_request(self):
        request_input = self.injector.get(SearchDirectoryInput)
        self.logger.info(f"searching for {request_input}")
        request_output = self.directory.search_directory(request_input)
        return jsonify(request_output.dict(by_alias=True))


@app_module.route("/health")
def health(request: Request):
    request.get_data()
    status = {"ready": "ready" in request.args}
    return jsonify(status)


app_module.add_url_rule("/search", view_func=Search.as_view("search"))


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


def create_app_injector() -> Injector:
    modules = [ApplicationConfigInjectorModule, UtilityInjectorModule]
    return Injector(modules=modules)


def create_app(injector: Optional[Injector] = None):
    bootstrap_injector = injector or create_app_injector()
    config_loader = bootstrap_injector.get(YAMLSettingsLoader)
    # This must come BEFORE the app instance is created
    logger_settings = config_loader.load_settings("logging")
    dictConfig(logger_settings)
    gunicorn_error_logger = logging.getLogger("gunicorn.error")

    # We've done our pre-work; now we can create the instance itself.
    app = Flask(__name__)
    app.register_blueprint(app_module)
    gunicorn_error_logger.debug(f"Adding gunicorn log handlers to {app}")
    app.logger.handlers = gunicorn_error_logger.handlers
    bootstrap_injector.binder.bind(logging.Logger, app.logger, scope=singleton)

    # This must come AFTER all blueprints have been registered!
    # (*And yes, it's OK this isn't being returned. It is now preserved on the app instance.)
    FlaskInjector(app=app, injector=bootstrap_injector)
    attach_app_error_handlers(app)
    return app


if __name__ == "__main__":
    create_app().run()
