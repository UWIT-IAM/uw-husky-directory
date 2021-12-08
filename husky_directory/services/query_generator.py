from __future__ import annotations

from typing import Any, Iterable, Tuple, Union

from flask_injector import request
from injector import inject
from pydantic import BaseModel, EmailError, validate_email

from husky_directory.models.enum import AffiliationState, PopulationType
from husky_directory.models.pws import ListPersonsInput
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.auth import AuthService


class WildcardFormat:
    """
    Assists with the formatting of wildcard search terms that are supported by PWS. Provides methods who can
    accept any number of string arguments, joins those arguments with a space, and returns the format string
    provided in the method.
    """

    def __fmt__(fmt_str: str, *args, each=False):
        if each:
            return " ".join([fmt_str.format(a) for a in args])
        arg = " ".join(args)
        return fmt_str.format(arg)

    @staticmethod
    def begins_with(*args: str, each: bool = False) -> str:
        return WildcardFormat.__fmt__("{}*", *args, each=each)

    @staticmethod
    def contains(*args: str, each: bool = False) -> str:
        return WildcardFormat.__fmt__("*{}*", *args, each=each)

    @staticmethod
    def matches(*args: str, each: bool = False) -> str:
        return WildcardFormat.__fmt__("{}", *args, each=each)


Query = ListPersonsInput  # Aliasing this for brevity in the below definitions.
ArgFmt = WildcardFormat  # An uglier, but shorter name


class GeneratedQuery(BaseModel):
    description: str
    request_input: ListPersonsInput


@request
class SearchQueryGenerator:
    """
    This is a really heavy, un-fun, hard-coded class that should not be maintained long-term. It only exists
    to provide first-iteration parity with the legacy https://github.com/uwit-iam/whitepages-ui.

    Given a string submitted as a name, this runs several permutations of queries based on how many terms are in the
    search, attempting to guess at which terms are supposed to be the first, "middle" or last names. Since there
    isn't really a concept of a "middle" name, though, and since the registrar/HR/etc. may treat them or enter them
    differently, we have to perform quite a few different queries.

    Ultimately what we should do is simply provide guidance on how to use wildcards so that users can build their
    own queries and we don't have to do any guesswork. But the change process might be lengthy, as it would be a
    departure from a known public UX. (Even though the implementation would be even easier than this,
    there are still front-end design decisions to weigh before making a decision like that.)
    """

    # These are just hard-coded templates for the 1- and 2-arg scenarios ("Madonna," "Retta," "Jeff Goldbum")
    # We could add hard-coded templates for higher-cardinality searches, but instead, it's better to just
    # autogenerate them. See also: _generate_sliced_name_queries().
    @inject
    def __init__(self, auth: AuthService):
        self.auth = auth

    def generate_department_queries(
        self, department: str, include_alt_queries: bool = True
    ) -> Tuple[str, ListPersonsInput]:
        """
        Generates queries for department.
        :param department:  The department query.
        :param include_alt_queries:  If set to True, will expand the search beyond the user input in an attempt to
        return all relevant results. Currently, this will simply sub "&" for "and" and vice versa, so that users
        don't need to keep track of this themselves.
        :return:
        """
        yield GeneratedQuery(
            description=f'Department matches "{department}"',
            request_input=ListPersonsInput(department=department),
        )

        if (
            "*" in department
        ):  # If the user provides a wildcard, we'll let PWS do the rest of the work.
            return

        yield GeneratedQuery(
            description=f'Department begins with "{department}"',
            request_input=ListPersonsInput(department=ArgFmt.begins_with(department)),
        )
        yield GeneratedQuery(
            description=f'Department contains "{department}"',
            request_input=ListPersonsInput(department=ArgFmt.contains(department)),
        )

        if not include_alt_queries:
            return

        # Add spaces to account for words with 'and' in them.
        if " and " in department:
            department = department.replace(" and ", " & ")
        elif "&" in department:
            department = department.replace("&", " and ")
        else:
            return  # Don't run additional queries if an 'and' isn't included in the q.

        # Remove any extra whitespace between words.
        department = " ".join(filter(bool, department.split()))
        yield from self.generate_department_queries(
            department, include_alt_queries=False
        )

    @staticmethod
    def generate_sanitized_phone_queries(phone: str) -> Tuple[str, ListPersonsInput]:
        """
        Attempts to match the phone exactly as provided; if the phone number was very long, we'll also try to match
        only the last 10 digits.

        Right now, PWS only supports phone number searches, and won't return results for pagers, faxes, etc.
        This is a regression from the previous directory product that allowed pager searches.

        :param phone: The phone number (digits only)
        """
        yield GeneratedQuery(
            description=f'Phone matches "{phone}"',
            request_input=ListPersonsInput(phone_number=phone),
        )
        if len(phone) > 10:  # XXX YYY-ZZZZ
            no_country_code = phone[-10:]
            yield GeneratedQuery(
                description=f'Phone matches "{no_country_code}"',
                request_input=ListPersonsInput(phone_number=no_country_code),
            )

    @staticmethod
    def generate_box_number_queries(box_number: str) -> Tuple[str, ListPersonsInput]:
        # PWS only ever returns "begins with" results for mailstop.
        yield GeneratedQuery(
            description=f'Mailstop begins with "{box_number}"',
            request_input=ListPersonsInput(mail_stop=box_number),
        )
        # All (most?) UW mail stops start with '35,' and so it is considered shorthand to omit
        # them at times. To be sure we account for shorthand input, we will also always try
        # adding '35' to every query.
        alt_number = f"35{box_number}"
        yield GeneratedQuery(
            description=f'Mailstop begins with "35{alt_number}"',
            request_input=ListPersonsInput(mail_stop=alt_number),
        )

    @staticmethod
    def generate_name_queries(name):
        """
        We only execute this if a user has given  us a name
        with a wildcard in it. Otherwise, the wildcard/reducer strategy is used.
        """
        if "*" in name:
            yield GeneratedQuery(
                description=f'Name matches "{name}"',
                request_input=ListPersonsInput(display_name=name),
            )
        if not name.startswith("*"):
            yield GeneratedQuery(
                description=f'Name includes "{name}"',
                request_input=ListPersonsInput(display_name=f"*{name}"),
            )

    @staticmethod
    def generate_email_queries(partial: str) -> Tuple[str, ListPersonsInput]:
        # If a user has supplied a full, valid email address, we will search only for the complete
        # listing as an 'is' operator.
        try:
            username, _ = validate_email(partial)
            # Decide whether we want to help the user by also including an alternate
            # domain in their query.
            alternate = None
            if partial.endswith("@uw.edu"):
                alternate = "washington.edu"
            elif partial.endswith("@washington.edu"):
                alternate = "uw.edu"
            yield GeneratedQuery(
                description=f'Email is "{partial}"',
                request_input=ListPersonsInput(email=partial),
            )
            if alternate:
                alternate_email = f"{username}@{alternate}"

                yield GeneratedQuery(
                    description=f'Email is "{alternate_email}"',
                    request_input=ListPersonsInput(email=alternate_email),
                )
            return
        except EmailError:
            pass

        # If the user includes a partial with '@' or '*', we assume they
        # just want to run this specific query, so will not forcibly include
        # any additional results.
        if "@" in partial or "*" in partial:  # If a user types in a full address
            yield GeneratedQuery(
                description=f'Email matches "{partial}"',
                request_input=ListPersonsInput(email=partial),
            )
        else:
            # If the user has just supplied 'foo123', we will search for a couple of
            # combinations.
            yield GeneratedQuery(
                description=f'Email begins with "{partial}"',
                request_input=ListPersonsInput(
                    email=WildcardFormat.begins_with(partial)
                ),
            )
            yield GeneratedQuery(
                description=f'Email contains "{partial}"',
                request_input=ListPersonsInput(email=WildcardFormat.contains(partial)),
            )

    def generate_field_queries(
        self, field_name: str, query_value: Any, population: Union[PopulationType, str]
    ) -> GeneratedQuery:
        if isinstance(population, str):
            population = PopulationType(population)

        query_method = f"generate_{field_name}_queries"
        generated: GeneratedQuery
        for generated in getattr(self, query_method)(query_value):
            if population in (PopulationType.all, PopulationType.employees):
                yield generated
            # We cannot perform an OR search for student/employee
            # affiliation state. In order to get a union of
            # students and employees, we must make an additional query.
            if (
                population in (PopulationType.all, PopulationType.students)
                and self.auth.request_is_authenticated
            ):
                yield GeneratedQuery(
                    description=generated.description,
                    request_input=generated.request_input.copy(
                        update=dict(
                            employee_affiliation_state=None,
                            student_affiliation_state=AffiliationState.current.value,
                        )
                    ),
                )

    def generate(
        self,
        request_input: SearchDirectoryInput,
    ) -> Iterable[GeneratedQuery]:
        population = request_input.population
        for field in ("name", "sanitized_phone", "box_number", "email", "department"):
            val = getattr(request_input, field, None)
            if val:
                yield from self.generate_field_queries(field, val, population)
