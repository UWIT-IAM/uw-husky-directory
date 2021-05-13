from flask_injector import request
from injector import inject
from werkzeug.local import LocalProxy


@request
class AuthService:
    """
    A simple little service to tell you whether or not
    the current request has been authenticated.
    """

    @inject
    def __init__(self, session: LocalProxy):
        self.session = session

    @property
    def request_is_authenticated(self) -> bool:
        return bool(self.session.get("uwnetid"))
