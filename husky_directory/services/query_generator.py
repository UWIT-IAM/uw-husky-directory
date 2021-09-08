from __future__ import annotations

from functools import partial
from itertools import product
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

import inflection
from flask_injector import request
from injector import inject
from pydantic import BaseModel, EmailError, validate_email

from husky_directory.models.common import RecordConstraint
from husky_directory.models.enum import AffiliationState, PopulationType
from husky_directory.models.pws import ListPersonsInput
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.auth import AuthService
from husky_directory.util import ConstraintPredicates


class QueryTemplate(BaseModel):
    """
    Due to the combinatoric complexity of some of our existing name queries, it's less
    maintenance (and less wrist strain) to simply generate our queries, rather than hard-code them.
    """

    # This string should describe what the query "scenario" is, and should
    # (by default) accept as many format placeholders (`{}`) as there will be
    # args supplied by the caller.
    # Example:
    #   Good:  'a: {}, b: {}, c: {}' when called against [1, 2, 3] or ['zebra', 'bottle', 'phone']
    #   Bad:                   . . . when called against [1] or ['bottle', 'phone', 'tablet', 'monkey']
    #
    # However, if you want to have more control over this, you can supply the description_formatter function.
    description_fmt: str

    # Allows you to change how your description is formatted based on the expected arguments.
    # For example, if you want to accept a variable number of arguments, or recombine the arguments,
    # you can provide a function to do so.
    #       Given a description_formatter of: lambda first, *others: (first, " ".join(others))
    #       and a description_fmt of: "First name {}, other terms: {}"
    #       when called against ["Mary", "J", "Blige"]
    #       the result would be: ["Mary", "J Blige"]
    # See tests/services/test_query_generator.py for more examples.
    description_formatter: Optional[Callable[[str], Iterable[str]]]

    # The query generator is similar to the description formatter, but creates a query based on the
    # provided arguments instead. For example, continuing the "Mary J Blige" example:
    #       Given a query_generator of: lambda first, *others: Query(first_name=first, last_name=' '.join(others))
    #       then the result would be: Query(first_name="Mary", last_name="J Blige")
    # See tests/services/test_query_generator.py for more examples
    query_generator: Callable[  # A function or other callable
        [str],  # That takes a list of strings (the "words" of the query)
        ListPersonsInput,  # and returns the query itself based on those args.
    ]

    # Constraints can be set as an added value to filter the output.
    # Constraints are not sent to PWS, but are used by PersonWebServiceClient to
    # add additional filters to the output.
    constraints: List[RecordConstraint] = []

    def get_query(self, args: List[str]) -> ListPersonsInput:
        """Given a list of arguments, creates a query by calling the query generator."""
        return self.query_generator(*args)

    def get_description(self, args: List[str]) -> str:
        """
        Given a list of arguments, creates a human-readable description of the query by calling the
        description_formatter, if it exists. Otherwise, simply uses the string.format() function with the
        args as-is.
        """
        if self.description_formatter:
            return self.description_fmt.format(*self.description_formatter(*args))
        return self.description_fmt.format(*args)


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
    name_query_templates = {
        1: [
            QueryTemplate(
                description_fmt='Last name is "{}"',
                query_generator=lambda name: Query(
                    last_name=name,
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredSurname",
                            predicate=partial(
                                ConstraintPredicates.null_or_matches, name
                            ),
                        )
                    ],
                ),
            ),
            QueryTemplate(
                description_fmt='Last name begins with "{}"',
                query_generator=lambda name: Query(
                    last_name=ArgFmt.begins_with(name),
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredSurname",
                            predicate=partial(
                                ConstraintPredicates.null_or_begins_with, name
                            ),
                        )
                    ],
                ),
            ),
            QueryTemplate(
                description_fmt='First name is "{}"',
                query_generator=lambda name: Query(
                    first_name=name,
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredFirstName",
                            predicate=partial(
                                ConstraintPredicates.null_or_matches, name
                            ),
                        )
                    ],
                ),
            ),
            QueryTemplate(
                description_fmt='Name contains: "{}"',
                query_generator=lambda name: Query(
                    display_name=ArgFmt.contains(name),
                    constraints=[
                        RecordConstraint(
                            namespace="DisplayName",
                            predicate=partial(
                                ConstraintPredicates.null_or_includes, name
                            ),
                        )
                    ],
                ),
            ),
        ],
        2: [
            QueryTemplate(
                description_fmt='First name is "{}", last name is "{}"',
                query_generator=lambda first, last: Query(
                    first_name=first,
                    last_name=last,
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredFirstName",
                            predicate=partial(
                                ConstraintPredicates.null_or_matches, first
                            ),
                        ),
                        RecordConstraint(
                            namespace="PreferredSurname",
                            predicate=partial(
                                ConstraintPredicates.null_or_matches, last
                            ),
                        ),
                    ],
                ),
            ),
            QueryTemplate(
                description_fmt='First name begins with "{}", last name is "{}"',
                query_generator=lambda first, last: Query(
                    first_name=ArgFmt.begins_with(first),
                    last_name=last,
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredFirstName",
                            predicate=partial(
                                ConstraintPredicates.null_or_begins_with, first
                            ),
                        ),
                        RecordConstraint(
                            namespace="PreferredSurname",
                            predicate=partial(
                                ConstraintPredicates.null_or_matches, last
                            ),
                        ),
                    ],
                ),
            ),
            QueryTemplate(
                description_fmt='First name is "{}", last name begins with "{}"',
                query_generator=lambda first, last: Query(
                    first_name=first,
                    last_name=ArgFmt.begins_with(last),
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredFirstName",
                            predicate=partial(
                                ConstraintPredicates.null_or_matches, first
                            ),
                        ),
                        RecordConstraint(
                            namespace="PreferredSurname",
                            predicate=partial(
                                ConstraintPredicates.null_or_begins_with, last
                            ),
                        ),
                    ],
                ),
            ),
            QueryTemplate(
                description_fmt='First name begins with "{}", last name begins with "{}"',
                query_generator=lambda first, last: Query(
                    first_name=ArgFmt.begins_with(first),
                    last_name=ArgFmt.begins_with(last),
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredFirstName",
                            predicate=partial(
                                ConstraintPredicates.null_or_begins_with, first
                            ),
                        ),
                        RecordConstraint(
                            namespace="PreferredSurname",
                            predicate=partial(
                                ConstraintPredicates.null_or_begins_with, last
                            ),
                        ),
                    ],
                ),
            ),
            QueryTemplate(
                description_fmt='Last name begins with "{} {}"',
                query_generator=lambda *args: Query(
                    last_name=ArgFmt.begins_with(*args),
                    constraints=[
                        RecordConstraint(
                            namespace="PreferredFirstName",
                            predicate=partial(
                                ConstraintPredicates.null_or_begins_with, " ".join(args)
                            ),
                        ),
                    ],
                ),
            ),
        ],
    }

    @inject
    def __init__(self, auth: AuthService):
        self.auth = auth

    @staticmethod
    def _build_sliced_name_query_template(
        slice: int = 1,
        pre_slice_format=ArgFmt.matches,
        post_slice_format=ArgFmt.matches,
    ) -> QueryTemplate:
        post_slice_label = "rest"
        if slice == 1:
            pre_slice_label = "First name"
        else:
            pre_slice_label = "First/middle name"

        pre_slice_query_name = inflection.humanize(pre_slice_format.__name__)
        post_slice_query_name = inflection.humanize(post_slice_format.__name__)

        def _generate_query(*args: str):
            first_name = pre_slice_format(*args[0:slice])
            last_name = post_slice_format(*args[slice:])
            return Query(
                first_name=first_name,
                last_name=last_name,
                constraints=[
                    RecordConstraint(
                        namespace="PreferredFirstName",
                        predicate=partial(
                            ConstraintPredicates.null_or_begins_with, first_name
                        ),
                    ),
                    RecordConstraint(
                        namespace="PreferredSurname",
                        predicate=partial(
                            ConstraintPredicates.null_or_begins_with, last_name
                        ),
                    ),
                ],
            )

        # Ugh; this is so ugly, but it beat hard-coding all of these use cases. I don't have the stamina to type
        # that much. See the QueryTemplate documentation for deeper details.
        return QueryTemplate(
            # The end result of the description looks like:
            #   'First name begins with "Husky", rest matches "Dawg"'
            # (or any permutations thereof)
            description_fmt=f'{pre_slice_label} {pre_slice_query_name} "{{}}", '
            f'{post_slice_label} {post_slice_query_name} "{{}}"',
            # Here we split and rejoin the args at their slice index, creating two total sets of arguments;
            # one acting as the "first name," and the other acting as the "last name." Either or both may contain
            # wildcards, or be blank. See the tests/services/test_query_generator.py for examples.
            description_formatter=lambda *args: (
                " ".join(args[0:slice]),
                " ".join(args[slice:]),
            ),
            # This is similar to the description_formatter, except it's formatting those same
            # slices with the *_slice_format function parameters.
            # See tests/services/test_query_generator.py for examples.
            query_generator=_generate_query,
        )

    def _generate_sliced_name_queries(self, max_slice: int) -> Iterable[QueryTemplate]:
        scenario_components = list(
            product([ArgFmt.matches, ArgFmt.begins_with], repeat=2)
        )

        # This generates query templates whose generator functions will iteratively slice the
        # array of args into the "first"/"last" combinations.
        #   Example:
        #       ["a", "b", "c"] => (
        #           ["a", "b c"],
        #           ["a b", "c"],
        #       )
        for i in range(1, max_slice):
            for pre_format, post_format in scenario_components:
                yield self._build_sliced_name_query_template(
                    slice=i, pre_slice_format=pre_format, post_slice_format=post_format
                )

        # After we do our combinatorics above, we move onto any other general query templates we want to add.
        yield QueryTemplate(
            # End result looks like:
            #   Name parts begin with: a/b/c
            description_fmt="Name parts begin with: {}",
            description_formatter=lambda *args: ("/".join(args),),
            # Generates a query that looks like: "a* b* c*"
            query_generator=lambda *args: Query(
                display_name=ArgFmt.begins_with(*args, each=True)
            ),
        )

    def generate_name_queries(self, name: str) -> Tuple[str, ListPersonsInput]:
        # No matter the case, we will always be checking for an exact match
        yield GeneratedQuery(
            description=f'Name matches "{name}"',
            request_input=ListPersonsInput(display_name=name),
        )

        # If the request contains a wildcard, we don't make any further "guesses" as to
        # what the user wants, because they've told us they think they know what they're doing.
        # This saves us a lot of queries and guesswork.
        if "*" in name:
            return

        name_parts = name.split()
        cardinality = len(name_parts)

        if cardinality in self.name_query_templates:
            for template in self.name_query_templates[cardinality]:
                yield GeneratedQuery(
                    description=template.get_description(name_parts),
                    request_input=template.get_query(name_parts),
                )
            return

        for template in self._generate_sliced_name_queries(cardinality):
            yield GeneratedQuery(
                description=template.get_description(name_parts),
                request_input=template.get_query(name_parts),
            )

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
