import logging

from flask import Blueprint, Request, jsonify, render_template


class AppBlueprint(Blueprint):
    """Blueprint for root urls within the application."""

    def __init__(self):
        super().__init__("uw-directory", __name__)
        self.add_url_rule("/", view_func=self.index)
        self.add_url_rule("/health", view_func=self.health)

    @staticmethod
    def index(request: Request, logger: logging.Logger):
        logger.info(f"Someone is here: {request}")
        return render_template("index.html")

    @staticmethod
    def health(request: Request):
        request.get_data()
        status = {"ready": "ready" in request.args}
        return jsonify(status)
