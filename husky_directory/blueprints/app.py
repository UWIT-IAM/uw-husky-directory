from typing import Optional

from flask import Blueprint, Request, jsonify, render_template
from injector import inject
from pydantic import BaseModel, Extra
from werkzeug.local import LocalProxy

from husky_directory.app_config import ApplicationConfig
from husky_directory.util import camelize


class HealthReport(BaseModel):
    class Config:
        alias_generator = camelize
        extra = Extra.ignore
        allow_population_by_field_name = True

    ready: bool
    build_id: Optional[str]
    start_time: str


class AppBlueprint(Blueprint):
    """Blueprint for root urls within the application."""

    @inject
    def __init__(self, app_config: ApplicationConfig):
        super().__init__("uw-directory", __name__)
        self.add_url_rule("/", view_func=self.index)
        self.add_url_rule("/health", view_func=self.health)
        self.build_id = app_config.build_id
        self.start_time = app_config.start_time
        self._app_config = app_config

    @staticmethod
    def index(request: Request, session: LocalProxy):
        return render_template("index.html", uwnetid=session.get("uwnetid"))

    def health(self, request: Request):
        report = HealthReport(
            ready="ready"
            in request.args,  # Someday maybe this will do something, now it just pretends to
            build_id=self.build_id,
            start_time=self.start_time.strftime("%y-%m-%d %H:%M:%S"),
        )
        return jsonify(report.dict())
