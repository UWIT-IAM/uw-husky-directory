"""
Models that are shared by more than one service. These should be
bare-bones models that do not define specialized behavior unless
the behavior itself is truly common. Otherwise, those behaviors
should be declared in an inheriting subclass within the context of
the respective service model.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any, Callable, Generic, Optional, TypeVar, Union

from pydantic import BaseModel, validator
from pydantic.generics import GenericModel


class UWDepartmentRole(BaseModel):
    """Denotes that an identity has some role within the UW (e.g., a job title, or class level)."""

    class Config:
        orm_mode = True

    title: str
    department: str


namespace_regex = re.compile(r"^([\w\d_]+\.?)+$")


class RecordNamespace(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v) -> RecordNamespace:
        if v and (not namespace_regex.match(v) or v.endswith(".")):
            raise ValueError(
                "Constraint namespace must be in the format: `attr_1.attr_2.attr_3`"
            )
        return v


T = TypeVar("T")


class RecordConstraint(GenericModel, Generic[T]):
    """
    This model helps us apply additional client-side filters to
    result records. A record can be an object or a dict.

    This allows fine-grained filtering control, which in our
    case here allows us to filter our records based on constraints
    that cannot be directly queried in PWS.

    `namespace` is a dot-notated path to the attribute
    being tested for a given record.

    `predicate` is a function that accepts some argument
    and returns a boolean result. At runtime, the value
    will be extracted from the record, using its namespace,
    and the result will be returned.

    `failure_callback` is an alternative to rejecting a record,
    and if set has the opportunity to update the record. This can
    allow filtering of specific attributes inside the record without
    rejecting the record itself. If the function does not return a
    value of True, the output will still be rejected!

    Example:
        data_1 = {"foo": {"bar": "baz" } }
        data_2 = {"foo": {"bar": None } }

        def callback(record: PersonOutput):
            record['foo']['bar'] = 'temp'
            return True

        predicate = lambda x: x == 'baz'

        constraint = RecordConstraint(
            namespace = 'foo.bar',
            predicate=predicate,
            failure_callback
        )

        assert onstraint.matches(data_1)
        assert data_1['foo']['bar'] == 'baz'

        assert constraint.matches(data_2)
        assert data_2['foo']['bar'] == 'temp'
    """

    namespace: Union[
        RecordNamespace, str
    ]  # Will always be converted to a RecordNamespace
    predicate: Callable[[T], bool] = lambda _: False
    failure_callback: Callable[[T], bool] = lambda _: False

    def resolve_namespace(self, record: Any) -> Optional[Any]:
        """
        Given a record, resolves the value of the namespace. The record can be anything.
        If it is a dict, the dict will be evaluated as namespace for the scope of this method.

        This will never fail to resolve; at worst, the value will be None.
        This is by design, although strict resolution could be added as a feature in the
        future if needed. It is heavy to do so, and not needed today.
        :param record: The thing you want to test; it can be anything!
        :return: The value of the resolved namespace, or None.
        """
        if isinstance(record, dict):
            # Converts the dict into an object.
            record = json.loads(
                json.dumps(record), object_hook=lambda item: SimpleNamespace(**item)
            )

        resolved = record

        for token in self.namespace.split("."):
            resolved = getattr(resolved, token, None)
            if not resolved:
                break
        return resolved

    def matches(self, record: T) -> bool:
        """
        Given a thing, returns whether the thing matches the predicate
        or the failure callback.
        :param record: The thing you want to filter.
        :return: Whether or not the test(s) succeeded.
        """
        resolved = self.resolve_namespace(record)
        return self.predicate(resolved) or self.failure_callback(record)

    @validator("namespace", always=True)
    def validate_namespace(cls, v: Union[str, RecordNamespace]) -> RecordNamespace:
        if not isinstance(v, RecordNamespace):
            return RecordNamespace.validate(v)
        return v
