import inflection
import pytest

from husky_directory.models.base import PropertyBaseModel


class _TestModel(PropertyBaseModel):
    @property
    def foo_bar(self) -> str:
        return "baz"


class AliasTestModel(_TestModel):
    class Config:
        @staticmethod
        def camelize_(v) -> str:
            return inflection.camelize(v, uppercase_first_letter=False)

        alias_generator = camelize_


def test_property_model_dict_default_includes_property():
    assert _TestModel().dict() == {"foo_bar": "baz"}


def test_property_model_exports_alias():
    assert AliasTestModel().dict(by_alias=True) == {"fooBar": "baz"}


def test_property_model_fails_no_alias_generator():
    with pytest.raises(AttributeError):  # No generator for property alias
        _TestModel().dict(by_alias=True)


def test_property_model_dict_explicitly_includes_property():
    assert _TestModel().dict(include={"foo_bar"}) == {"foo_bar": "baz"}


def test_property_model_dict_explicitly_excludes_property():
    assert _TestModel().dict(exclude={"foo_bar"}) == {}
