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
