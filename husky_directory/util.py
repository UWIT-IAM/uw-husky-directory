from __future__ import annotations

import functools
import logging
import time
import os
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

import inflection
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics

from husky_directory.logging import ROOT_LOGGER, build_extras

if os.environ.get("GUNICORN_LOG_LEVEL", None):
    MetricsClientCls = GunicornInternalPrometheusMetrics
else:
    MetricsClientCls = PrometheusMetrics


def camelize(string: str, uppercase_first_letter=False) -> str:
    """Fixes the default behavior to keep the first character lowerCased."""
    return inflection.camelize(string, uppercase_first_letter=uppercase_first_letter)


class MetricsClient(MetricsClientCls):
    """
    This class simply aliases its much more unwieldy
    parent-class, so that it's easier to inject throughout
    our application:

        injector.get(MetricsClient)
    is an alias for
        injector.get(GunicornInternalPrometheusMetrics).

    Also:

        @inject
        class Foo:
            def __init__(self, metrics: MetricsClient):
                self.metrics = metrics
    """

    pass


T = TypeVar("T")


class ConstraintPredicates:
    """Commonly used predicates for output constraints"""

    @staticmethod
    def normalize_strings(*args: T) -> T:
        for arg in args:
            if isinstance(arg, str):
                yield arg.lower()
            else:
                yield arg

    @staticmethod
    def null_or_begins_with(target: str, value: str) -> bool:
        target, value = ConstraintPredicates.normalize_strings(target, value)
        return not value or value.startswith(target)

    @staticmethod
    def null_or_matches(target: str, value: str) -> bool:
        target, value = ConstraintPredicates.normalize_strings(target, value)
        return not value or value == target

    @staticmethod
    def matches(target: str, value: str) -> bool:
        target, value = ConstraintPredicates.normalize_strings(target, value)
        return target == value

    @staticmethod
    def null_or_includes(target: str, value: str) -> bool:
        target, value = ConstraintPredicates.normalize_strings(target, value)
        if isinstance(value, (list, set)):
            value = list(ConstraintPredicates.normalize_strings(*value))
        return not value or target in value


class Timer:
    """
    This timer integrates with logging and also offers a timed context
    to make it easy to time functions or even just blocks of code with
    minimal setup.

    All messages go to the 'app.timer' log so they can easily be filtered.
    Additionally, if passing through husky_directory.JsonFormatter
    the timing information will be included as extra data in the JSON log,
    making it possible to easily find a given timer and scope queries around
    the magnitude of its results.

    For more information, see docs/logging.md

    # Easiest use:
        with Timer('my-timer'):
            do_work()

    # Disable logging at will to just use the timing (but why?):
        with Timer('my-timer', emit_log=False) as t:
            do_work()
        if t.result > 5:
            logger.warning('Took too long!')

    # Repeated use:

    timer = Timer('my-timer')
    with timer.run(emit_log=False) as t:
        do_some_work()
    if t.result > 5:
        with timer.run(emit_log=True):
            do_some_other_work_and_log_it()

    # Manual use:
        timer = Timer('my-timer')
        timer.start()
        do_work()
        timer.stop(emit_log=True)  # redundant; true by default
    """

    logger_name: str = "app.timer"
    precision: int = 3

    def __init__(
        self, name: str, emit_log: bool = True, context: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.logger = logging.getLogger(ROOT_LOGGER).getChild(self.logger_name)
        self.start_time = None
        self.end_time = None
        self.result = None
        self.emit_log_on_stop = emit_log
        self.context = context or {}

    def start(self) -> Timer:
        self.start_time = time.time()
        return self

    def stop(self, emit_log: Optional[bool] = None) -> Timer:
        # If the caller does not pass an option in, use the class default.
        emit_log = emit_log if emit_log is not None else self.emit_log_on_stop
        self.end_time = time.time()
        self.result = round(self.end_time - self.start_time, self.precision)
        if emit_log:
            self._emit_log()
        return self

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    @contextmanager
    def run(self, emit_log: bool = True) -> Timer:
        self.start()
        yield self
        self.stop(emit_log=emit_log)

    def _emit_log(self):
        summary = {
            "name": self.name,
            "timerResult": self.result,
            "startTime": self.start_time,
            "endTime": self.end_time,
        }
        self.context["timer"] = summary
        extras = build_extras(self.context)
        self.logger.info(f"{self.name} [{self.result}] {self.context}", extra=extras)


def timed(function: Callable):
    """
    Decorator that can be applied to functions to time them.
    Timer logs go to the [gunicorn.error.]app.timer log.
    For more, see Timer.
    """

    @functools.wraps(function)
    def inner(*args, **kwargs):
        timer = Timer(f"{function.__module__}#{function.__name__}")
        with timer.run():
            result = function(*args, **kwargs)
        return result

    return inner
