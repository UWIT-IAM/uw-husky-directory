from typing import TypeVar

import inflection
from devtools.debug import PrettyFormat
from injector import Module, provider, singleton


class UtilityInjectorModule(Module):
    @singleton
    @provider
    def provide_pretty_formatter(self) -> PrettyFormat:
        """
        Uses devtools PrettyFormat to make it easier to log models and objects readably. This singleton formatter
        can be used application wide for consistency.

        Example:

            obj = dict(foo=123, bar=234)
            print(injector.get(PrettyFormat)(obj))
        """
        return PrettyFormat(simple_cutoff=0)  # Always show list items 1 per line.


def camelize(string: str, uppercase_first_letter=False) -> str:
    """Fixes the default behavior to keep the first character lowerCased."""
    return inflection.camelize(string, uppercase_first_letter=uppercase_first_letter)


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
