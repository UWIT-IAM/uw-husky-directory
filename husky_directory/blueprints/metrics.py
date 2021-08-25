from flask import Blueprint
from injector import inject


class MetricsBlueprint(Blueprint):
    @inject
    def __init__(self):
        super().__init__("metrics", __name__, url_prefix="/metrics")
        self.add_url_rule("/", view_func=self.placeholder, methods=["GET"])

    def placeholder(self):
        return "OK"
