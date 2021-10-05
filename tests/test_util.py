import time
from importlib import reload
from unittest import mock

import pytest

import husky_directory.util


class TestConstraintPredicates:
    def test_normalize_strings(self):
        assert list(
            husky_directory.util.ConstraintPredicates.normalize_strings(
                "FOO", "fOo", 13, False, {"bAR": "baz"}
            )
        ) == ["foo", "foo", 13, False, {"bAR": "baz"}]

    @pytest.mark.parametrize(
        "target, value, expected",
        [
            ("foo", None, True),
            ("foo", "football", True),
            ("Foo", "fOo", True),
            ("foo", "oof", False),
        ],
    )
    def test_null_or_begins_with(self, target, value, expected):
        assert (
            husky_directory.util.ConstraintPredicates.null_or_begins_with(target, value)
            == expected
        )

    @pytest.mark.parametrize(
        "target, value, expected",
        [
            ("foo", None, True),
            ("Foo", "fOo", True),
            ("Foo", "football", False),
        ],
    )
    def test_null_or_matches(self, target, value, expected):
        assert (
            husky_directory.util.ConstraintPredicates.null_or_matches(target, value)
            == expected
        )

    @pytest.mark.parametrize(
        "target, value, expected",
        [
            ("foo", None, False),
            ("Foo", "fOo", True),
            ("Foo", "football", False),
        ],
    )
    def test_matches(self, target, value, expected):
        assert (
            husky_directory.util.ConstraintPredicates.matches(target, value) == expected
        )

    @pytest.mark.parametrize(
        "target, value, expected",
        [
            ("fOO", "pRouDFoot", True),
            ("foo", None, True),
            ("foo", "oof", False),
            ("Foo", ["FOo", "bar", "baz"], True),
        ],
    )
    def test_null_or_includes(self, target, value, expected):
        assert (
            husky_directory.util.ConstraintPredicates.null_or_includes(target, value)
            == expected
        )


class TestTimer:
    def _assert_timer_result(
        self, timer: husky_directory.util.Timer, expected_result: float = 0.25
    ):
        min_jitter = expected_result - 0.05
        max_jitter = expected_result + 0.05
        assert min_jitter <= round(timer.result, 2) <= max_jitter

    def test_timer_with_block(self):
        with husky_directory.util.Timer("my-timer") as timer:
            time.sleep(0.25)
        self._assert_timer_result(timer)

    def test_timer_with_run(self):
        timer = husky_directory.util.Timer("my-timer")
        with timer.run():
            time.sleep(0.25)
        self._assert_timer_result(timer)

    def test_assert_manual_timer(self):
        timer = husky_directory.util.Timer("my-timer")
        timer.start()
        time.sleep(0.25)
        timer.stop()
        self._assert_timer_result(timer)


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"GUNICORN_LOG_LEVEL": "DEBUG"}, "GunicornInternalPrometheusMetrics"),
        ({}, "PrometheusMetrics"),
    ],
)
def test_metrics_class_override(env, expected):
    import os

    with mock.patch.dict(os.environ, env, clear=True):
        reload(husky_directory.util)
        assert husky_directory.util.MetricsClientCls.__name__ == expected


@pytest.mark.parametrize(
    "sequence, expected",
    [
        (["foo"], '"foo"'),
        (["foo", "bar"], '"foo" and "bar"'),
        (["foo", "bar", "baz"], '"foo," "bar," and "baz"'),
    ],
)
def test_readable_list(sequence, expected):
    assert husky_directory.util.readable_list(sequence) == expected


@pytest.mark.parametrize("query, display_name,", [("aloe", "aloe vera")])
@pytest.mark.parametrize(
    "coefficient, expected",
    [(0, False), (0.25, False), (0.5, False), (0.75, True), (1, True)],
)
def test_is_similar(query, display_name, coefficient, expected):
    assert husky_directory.util.is_similar(query, display_name, coefficient) == expected
