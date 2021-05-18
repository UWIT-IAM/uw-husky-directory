import pytest

from husky_directory.util import ConstraintPredicates


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
