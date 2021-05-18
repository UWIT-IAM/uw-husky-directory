import pytest
from werkzeug.local import LocalProxy

from husky_directory.services.auth import AuthService


class TestAuthService:
    @pytest.fixture(autouse=True)
    def configure(self, mock_injected, injector):
        self.session = {}
        with mock_injected(LocalProxy, self.session):
            self.service = injector.get(AuthService)

    @pytest.mark.parametrize(
        "uwnetid, expected_result",
        [
            ("foo", True),
            (None, False),
        ],
    )
    def test_request_is_authenticated(self, uwnetid, expected_result):
        self.session["uwnetid"] = uwnetid
        assert self.service.request_is_authenticated == expected_result
