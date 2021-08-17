from logging import Logger
from typing import Optional

from flask import Blueprint, Request, jsonify, render_template
from injector import Injector, inject
from pydantic import BaseModel, Extra
from werkzeug.exceptions import InternalServerError
from werkzeug.local import LocalProxy

from husky_directory.app_config import ApplicationConfig
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.util import camelize


class HealthReport(BaseModel):
    class Config:
        alias_generator = camelize
        extra = Extra.ignore
        allow_population_by_field_name = True

    ready: bool
    version: Optional[str]
    start_time: str
    pws_is_ready: bool = False


class AppBlueprint(Blueprint):
    """Blueprint for root urls within the application."""

    @inject
    def __init__(
        self, app_config: ApplicationConfig, logger: Logger, injector: Injector
    ):
        super().__init__("uw-directory", __name__)
        self.add_url_rule("/", view_func=self.index)
        self.add_url_rule("/health", view_func=self.health)
        self.config = app_config
        self.start_time = app_config.start_time
        self._app_config = app_config
        self._injector = injector
        self.logger = logger

    @property
    def version(self) -> Optional[str]:
        return self.config.version

    @staticmethod
    def index(request: Request, session: LocalProxy):
        return render_template("index.html", uwnetid=session.get("uwnetid"))

    @property
    def pws_is_ready(self):
        try:
            self._injector.get(PersonWebServiceClient).validate_connection()
        except Exception as e:
            print(e)
            self.logger.error(f"{e.__class__}: {str(e)}")
            return False
        return True

    @property
    def ready(self) -> bool:
        """
        This should return a boolean that signifies the
        application is fully bootstrapped.
        """
        version_is_set = bool(self.version)
        return version_is_set and self.pws_is_ready

    def health(self, request: Request):
        report = HealthReport(
            ready=self.ready,
            version=self.version,
            pws_is_ready=self.pws_is_ready,
            start_time=self.start_time.strftime("%y-%m-%d %H:%M:%S"),
        )
        if "ready" in request.args:
            if not self.ready:
                raise InternalServerError(
                    f"Server is not ready to handle requests: {str(report)}"
                )
        return jsonify(report.dict())
