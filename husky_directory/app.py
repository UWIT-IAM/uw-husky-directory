from flask import Flask, Request, render_template
from flask.blueprints import Blueprint
import logging
from logging.config import dictConfig
from .app_config import get_log_config

from flask_injector import FlaskInjector

app_module = Blueprint("main", "app")
logger = logging.getLogger(__name__)


@app_module.route("/")
def index(request: Request):
    logger.info(f"Someone is here: {request}")
    return render_template("index.html")


def create_app():
    # This must come BEFORE the app instance is created
    dictConfig(get_log_config())
    gunicorn_error_logger = logging.getLogger("gunicorn.error")

    app = Flask(__name__)
    app.register_blueprint(app_module)
    gunicorn_error_logger.debug(f"Adding gunicorn log handlers to {app}")
    app.logger.handlers.extend(gunicorn_error_logger.handlers)
    # This must come AFTER all blueprints have been registered!
    FlaskInjector(app=app)
    return app
