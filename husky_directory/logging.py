import json
import logging
from typing import Optional, Type, TypeVar

from flask import Request
from injector import Injector
from werkzeug.local import LocalProxy

T = TypeVar("T")


class JsonFormatter(logging.Formatter):
    """
    A formatter adhering to the structure advised in
    https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry.
    """

    injector: Injector = None

    def _get_optional_injected(self, cls: Type[T]) -> Optional[T]:
        if not self.injector:
            return None
        try:
            return self.injector.get(cls)
        except RuntimeError:
            return None

    def get_request(self) -> Optional[Request]:
        return self._get_optional_injected(Request)

    def get_session(self) -> Optional[LocalProxy]:
        return self._get_optional_injected(LocalProxy)

    def format(self, record):
        data = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "line": f"{record.filename}#{record.funcName}:{record.lineno}",
        }
        request = self.get_request()
        if request:
            request_log = {
                "method": request.method,
                "url": request.url,
                "remoteIp": request.remote_addr,
            }
            session = self.get_session()
            if session and session.get("uwnetid"):
                request_log["uwnetid"] = session["uwnetid"]
            data["request"] = request_log

        return json.dumps(data, default=str)
