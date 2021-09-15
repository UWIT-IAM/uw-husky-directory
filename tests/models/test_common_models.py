import pytest
from pydantic import ValidationError

from husky_directory.models.common import RecordConstraint, RecordNamespace


class TestRecordConstraint:
    @pytest.mark.parametrize(
        "record",
        [
            {"foo": "bar", "baz": {"bop": "buzz"}},
        ],
    )
    @pytest.mark.parametrize(
        "namespace, expected_value",
        [
            ("foo", "bar"),
            ("foo.bar", None),  # Bar is not an attribute
            ("baz.bop", "buzz"),
        ],
    )
    def test_resolve_namespace(self, namespace, record, expected_value):
        constraint = RecordConstraint(
            namespace=namespace,
        )
        assert constraint.resolve_namespace(record) == expected_value

    @pytest.mark.parametrize("invalid_input", ["foo.", "foo-bar"])
    def test_invalid_namespace(self, invalid_input):
        with pytest.raises(ValidationError):
            RecordConstraint(namespace=invalid_input)

    @pytest.mark.parametrize("valid_input", ("foo.bar", RecordNamespace("foo.bar")))
    def test_valid_namespace(self, valid_input):
        RecordConstraint(namespace=valid_input)
