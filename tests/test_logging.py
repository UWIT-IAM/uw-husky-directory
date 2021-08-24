from unittest import mock
from unittest.mock import MagicMock

from flask import Request
from injector import Injector
from werkzeug.local import LocalProxy

from husky_directory.logging import JsonFormatter


def test_get_attrs_no_injector():
    formatter = JsonFormatter()
    assert formatter.get_session() is None
    assert formatter.get_request() is None


def test_get_attrs_injector_error(injector: Injector):
    formatter = JsonFormatter()
    formatter.injector = injector
    with mock.patch.object(injector, "get") as mock_get:
        mock_get.side_effect = RuntimeError
        assert formatter.get_session() is None
        assert formatter.get_request() is None


def test_formatter_late_injection(injector: Injector, client, mock_injected):
    formatter = JsonFormatter()
    formatter.injector = injector
    with mock_injected(LocalProxy, {}) as session:
        request = MagicMock(Request)
        request.method = "GET"
        request.url = "https://www.uw.edu"
        request.remote_addr = "127.0.0.1"
        session["uwnetid"] = "dawg"
        with mock_injected(Request, request):
            client.get("/")
            assert formatter.get_request().url == "https://www.uw.edu"
            assert formatter.get_session().get("uwnetid") == "dawg"
