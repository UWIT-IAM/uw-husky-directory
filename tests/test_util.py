import time

import pytest

from husky_directory.util import ConstraintPredicates, Timer


class TestConstraintPredicates:
    def test_normalize_strings(self):
        assert list(
            ConstraintPredicates.normalize_strings(
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
        assert ConstraintPredicates.null_or_begins_with(target, value) == expected

    @pytest.mark.parametrize(
        "target, value, expected",
        [
            ("foo", None, True),
            ("Foo", "fOo", True),
            ("Foo", "football", False),
        ],
    )
    def test_null_or_matches(self, target, value, expected):
        assert ConstraintPredicates.null_or_matches(target, value) == expected

    @pytest.mark.parametrize(
        "target, value, expected",
        [
            ("foo", None, False),
            ("Foo", "fOo", True),
            ("Foo", "football", False),
        ],
    )
    def test_matches(self, target, value, expected):
        assert ConstraintPredicates.matches(target, value) == expected

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
        assert ConstraintPredicates.null_or_includes(target, value) == expected


class TestTimer:
    def _assert_timer_result(self, timer: Timer, expected_result: float = 0.25):
        min_jitter = expected_result - 0.05
        max_jitter = expected_result + 0.05
        assert min_jitter <= round(timer.result, 2) <= max_jitter

    def test_timer_with_block(self):
        with Timer("my-timer") as timer:
            time.sleep(0.25)
        self._assert_timer_result(timer)

    def test_timer_with_run(self):
        timer = Timer("my-timer")
        with timer.run():
            time.sleep(0.25)
        self._assert_timer_result(timer)

    def test_assert_manual_timer(self):
        timer = Timer("my-timer")
        timer.start()
        time.sleep(0.25)
        timer.stop()
        self._assert_timer_result(timer)
