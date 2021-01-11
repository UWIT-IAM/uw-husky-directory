from itertools import product
from typing import Callable, Iterable, List, Optional, Tuple

import inflection
from injector import singleton
from pydantic import BaseModel

from husky_directory.models.pws import ListPersonsInput
from husky_directory.models.search import SearchDirectoryInput


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


@singleton
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
    query_templates = {
        1: [
            QueryTemplate(
                description_fmt='Last name is "{}"',
                query_generator=lambda name: Query(last_name=name),
            ),
            QueryTemplate(
                description_fmt='Last name begins with "{}"',
                query_generator=lambda name: Query(last_name=ArgFmt.begins_with(name)),
            ),
            QueryTemplate(
                description_fmt='First name is "{}"',
                query_generator=lambda name: Query(first_name=name),
            ),
            QueryTemplate(
                description_fmt='Name contains: "{}"',
                query_generator=lambda name: Query(display_name=ArgFmt.contains(name)),
            ),
        ],
        2: [
            QueryTemplate(
                description_fmt='First name is "{}", last name is "{}"',
                query_generator=lambda first, last: Query(
                    first_name=first, last_name=last
                ),
            ),
            QueryTemplate(
                description_fmt='First name begins with "{}", last name is "{}"',
                query_generator=lambda first, last: Query(
                    first_name=ArgFmt.begins_with(first), last_name=last
                ),
            ),
            QueryTemplate(
                description_fmt='First name is "{}", last name begins with "{}"',
                query_generator=lambda first, last: Query(
                    first_name=first, last_name=ArgFmt.begins_with(last)
                ),
            ),
            QueryTemplate(
                description_fmt='First name begins with "{}", last name begins with "{}"',
                query_generator=lambda first, last: Query(
                    first_name=ArgFmt.begins_with(first),
                    last_name=ArgFmt.begins_with(last),
                ),
            ),
            QueryTemplate(
                description_fmt='Last name begins with "{} {}"',
                query_generator=lambda *args: Query(
                    last_name=ArgFmt.begins_with(*args)
                ),
            ),
        ],
    }

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
            query_generator=lambda *args: Query(
                first_name=pre_slice_format(*args[0:slice]),
                last_name=post_slice_format(*args[slice:]),
            ),
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

    def generate_queries(self, name: str) -> Tuple[str, ListPersonsInput]:
        # No matter the case, we will always be checking for an exact match
        yield f'Name matches "{name}"', ListPersonsInput(display_name=name)

        # If the request contains a wildcard, we don't make any further "guesses" as to
        # what the user wants, because they've told us they think they know what they're doing.
        # This saves us a lot of queries and guesswork.
        if "*" in name:
            return

        name_parts = name.split()
        cardinality = len(name_parts)

        if cardinality in self.query_templates:
            for template in self.query_templates[cardinality]:
                yield template.get_description(name_parts), template.get_query(
                    name_parts
                )
            return

        for template in self._generate_sliced_name_queries(cardinality):
            yield template.get_description(name_parts), template.get_query(name_parts)

    def generate(
        self, request_input: SearchDirectoryInput
    ) -> Iterable[Tuple[str, ListPersonsInput]]:
        if request_input.name:
            for description, query in self.generate_queries(request_input.name):
                yield description, query
