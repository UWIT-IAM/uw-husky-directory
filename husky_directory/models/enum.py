# Nothing in this file should depend on anything except for stdlib enum.
# This is to prevent circular dependencies for low-level components.

from enum import Enum


class AffiliationState(Enum):
    """
    These are defined by PWS but only enumerated in their test UI:
    https://it-wseval1.s.uw.edu/identity/v2/person
    """

    current = "current"
    prior = "prior"
    exists = "current,prior"


class PopulationType(Enum):
    students = "students"
    employees = "employees"
    all = "all"


class ResultDetail(Enum):
    full = "full"
    summary = "summary"


class SearchType(Enum):
    # Old-school cool. It's inefficient but
    # very explicit.
    classic = "classic"

    # In active development, constantly striving to
    # provide more relevant results, faster!
    experimental = "experimental"
