import re
from typing import List, Optional

from inflection import humanize

from husky_directory.models.pws import NamedIdentity


class NameAnalyzer:
    _can_humanize_expr = re.compile("^[a-zA-Z]+$")

    def __init__(self, identity: NamedIdentity):
        self.identity = identity
        self.__normalized: Optional[NamedIdentity] = None
        self.__results = dict.fromkeys(
            {
                "displayed_surname",
                "displayed_first_name",
                "displayed_middle_name",
                "name_tokens",
                "canonical_tokens",
                "sort_key",
            },
            None,
        )

    @property
    def displayed_surname(self) -> str:
        """
        Some users have multiple tokens in their surname ("last name").
        Rather than always assuming that the last word of the name is the surname,
        we check the individual last_name/surname fields first so that we can
        capture multiple-word names.
        """
        key = "displayed_surname"
        if not self.__results[key]:
            display_name = self.normalized.display_name
            pref_last = self.normalized.preferred_last_name
            reg_last = self.normalized.registered_surname
            # If a user has set their preferred name, it will almost
            # certainly be part of their displayed name, unless something
            # is very wrong.
            if pref_last and pref_last in display_name:
                result = self.identity.preferred_last_name
            # If a user has not set a preferred name, their
            # registered surname will almost certainly be part of their
            # display name, so we use that.
            elif reg_last and reg_last in display_name:
                result = self.identity.registered_surname
            # But if neither the preferred nor the registered surname
            # are part of the user's display name (which should not happen!)
            # then we will assume the final "token" of the display name is
            # their surname.
            else:
                result = self.identity.display_name.split()[-1]
            self.__results[key] = result
        return self.__results[key]

    @property
    def displayed_first_name(self) -> str:
        """
        Some users have multiple tokens in their given name ("first name").
        Also, registered names combine first and  middle names, and therefore it is
        not possible to tell what is a "first" name and what is a "middle" name
        unless the user tells us by setting a preferred name.
        """
        key = "displayed_first_name"
        if not self.__results[key]:
            display_name = self.normalized.display_name
            last_name = self.normalize_name_tokens(self.displayed_surname)
            last_name_index = display_name.index(last_name)
            first_middle = display_name[:last_name_index]
            pref_first = self.normalized.preferred_first_name
            reg_first_middle = self.normalized.registered_first_middle_name

            # If the user has a preferred name set, and that name is in
            # the display_name, return the preferred first name
            if pref_first and pref_first in first_middle:
                result = self.identity.preferred_first_name
            # If the user has no preferred name set, but the registered name
            # is part of the display name, return everything except for the last
            # name from the display name.
            elif reg_first_middle and reg_first_middle in first_middle:
                result = self.identity.display_name[:last_name_index]
            # If all else fails, and our data is dirty, make the assumption that the user
            # has only a single-word first name, and that it's the first token of their
            # display name. (Rather than using the registered first_middle name, which may
            # include a middle name we don't want to assume is their first name.)
            else:
                result = self.identity.display_name.split()[0]
            self.__results[key] = result
        return self.__results[key]

    @property
    def displayed_middle_name(self) -> str:
        key = "displayed_middle_name"
        if self.__results[key] is None:  # The result may be an empty string
            pref_middle = self.normalized.preferred_middle_name
            display_name = self.normalized.display_name

            if pref_middle and pref_middle in display_name:
                result = self.identity.preferred_middle_name
            else:
                splice_index = len(self.displayed_first_name) + 1
                surname_index = self.identity.display_name.index(self.displayed_surname)
                result = self.identity.display_name[splice_index:surname_index]
            if not result or result not in self.identity.display_name:
                result = ""
            self.__results[key] = result

        return self.__results[key]

    @property
    def name_tokens(self) -> List[str]:
        key = "name_tokens"
        if not self.__results[key]:
            result = list(
                filter(
                    lambda i: bool(i),
                    [
                        self.displayed_first_name,
                        self.displayed_middle_name,
                        self.displayed_surname,
                    ],
                )
            )
            self.__results[key] = result
        return self.__results[key]

    @property
    def canonical_name_tokens(self) -> List[str]:
        """
        Reorders ["First", "Middle", "Last"] as ["Last", "First", "Middle"]
        """
        key = "canonical_tokens"
        if not self.__results[key]:
            result = self.name_tokens.copy()
            sort_seed = result.pop(-1)
            result.insert(0, sort_seed)
            self.__results[key] = result
        return self.__results[key]

    @property
    def sort_key(self) -> str:
        """
        "First Middle Last" becomes "last first middle" for lexical
        sorting purposes.
        """
        key = "sort_key"
        if not self.__results[key]:
            result = " ".join([i.lower() for i in self.canonical_name_tokens])
            self.__results[key] = result
        return self.__results[key]

    @classmethod
    def humanize(cls, val: str) -> str:
        """

        Don't use the humanize function for names with punctuation,
        as humanize may make them worse. For instance "Anne-marie"
        instead of "Anne-Marie".
        """
        if re.fullmatch(cls._can_humanize_expr, val):
            return humanize(val)
        return val

    @property
    def normalized(self) -> NamedIdentity:
        if not self.__normalized:
            normalized_keys = {
                "display_name",
                "registered_name",
                "registered surname",
                "registered_first_middle_name",
                "preferred_first_name",
                "preferred_middle_name",
                "preferred_last_name",
            }
            raw_values = self.identity.dict(include=normalized_keys)
            normalized = NamedIdentity.parse_obj(
                {k: self.normalize_name_tokens(v) for k, v in raw_values.items()}
            )
            self.__normalized = normalized
        return self.__normalized

    @classmethod
    def normalize_name_tokens(cls, value: str) -> str:
        """
        Because the data we receive from PWS may contain
        names with different casing, we have to normalize them.
        We split on spaces and humanize each so that each is
        capitalized; humanizing the entire string at once
        leads to some not-very namely results.

        Note: The display_name should only be normalized
        for comparative purposes, and never be preserved;
        we should always display the display name as is!
        """
        if value:
            return " ".join(cls.humanize(v) for v in value.split())
        return value
