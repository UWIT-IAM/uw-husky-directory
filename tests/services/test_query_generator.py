import pytest
from injector import Injector
from werkzeug.local import LocalProxy

from husky_directory.models.enum import PopulationType
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.query_generator import (
    SearchQueryGenerator,
    WildcardFormat,
)


@pytest.mark.parametrize(
    "fmt, expected",
    [
        (WildcardFormat.begins_with("foo"), "foo*"),
        (WildcardFormat.begins_with("foo", "bar"), "foo bar*"),
        (WildcardFormat.begins_with("foo", "bar", each=True), "foo* bar*"),
        (WildcardFormat.matches("foo"), "foo"),
        (WildcardFormat.contains("foo"), "*foo*"),
    ],
)
def test_wildcard_format(fmt, expected):
    assert fmt == expected


class TestSearchQueryGenerator:
    @pytest.fixture(autouse=True)
    def initialize(self, injector: Injector, mock_injected):
        self.injector = injector
        self.session = {}
        with mock_injected(LocalProxy, self.session):
            self.query_generator = injector.get(SearchQueryGenerator)
            yield

    def test_wildcard_input(self):
        generated = list(
            self.query_generator.generate(SearchDirectoryInput(email="foo*"))
        )
        assert len(generated) == 1
        assert generated[0].description == 'Email matches "foo*"'

    def test_phone_input_short_number(self):
        request_input = SearchDirectoryInput(phone="2065554321")
        queries = list(self.query_generator.generate(request_input))
        assert len(queries) == 1

    def test_phone_input_long_number(self):
        request_input = SearchDirectoryInput(phone="+1 (206) 555-4321")
        queries = list(self.query_generator.generate(request_input))
        assert queries[0].request_input.phone_number == "12065554321"
        assert queries[1].request_input.phone_number == "2065554321"
        assert len(queries) == 2

    def test_phone_input_invalid_number(self):
        request_input = SearchDirectoryInput(phone="abcdefg")
        assert request_input.phone
        assert not request_input.sanitized_phone

        queries = list(self.query_generator.generate(request_input))
        assert not queries

    def test_box_number_input(self):
        request_input = SearchDirectoryInput(box_number="123456")
        queries = list(self.query_generator.generate(request_input))
        assert len(queries) == 2
        assert queries[0].request_input.mail_stop == "123456"
        assert queries[1].request_input.mail_stop == "35123456"

    @pytest.mark.parametrize(
        "input_value, expected_snippets",
        [
            ("foo", ['begins with "foo"', 'contains "foo"']),
            ("foo@bar.com", ['is "foo@bar.com"']),
            ("foo@", ['matches "foo@"']),
            ("foo*", ['matches "foo*"']),
            ("foo@uw.edu", ['is "foo@uw.edu"', 'is "foo@washington.edu"']),
            ("foo@washington.edu", ['is "foo@washington.edu"', 'is "foo@uw.edu"']),
        ],
    )
    def test_email_input(self, input_value, expected_snippets):
        request_input = SearchDirectoryInput(email=input_value)
        queries = list(self.query_generator.generate(request_input))
        assert len(queries) == len(expected_snippets)
        for i, snippet in enumerate(expected_snippets):
            assert snippet in queries[i].description

    @pytest.mark.parametrize(
        "input_value, expected_snippets",
        [
            (
                "foo",
                [
                    'matches "foo"',
                    'begins with "foo"',
                    'contains "foo"',
                ],
            ),
            ("foo*", ['matches "foo*"']),
            (
                "foo & bar",
                [
                    'matches "foo & bar"',
                    'begins with "foo & bar"',
                    'contains "foo & bar"',
                    'matches "foo and bar"',
                    'begins with "foo and bar"',
                    'contains "foo and bar"',
                ],
            ),
            (
                "foo and bar",
                [
                    'matches "foo and bar"',
                    'begins with "foo and bar"',
                    'contains "foo and bar"',
                    'matches "foo & bar"',
                    'begins with "foo & bar"',
                    'contains "foo & bar"',
                ],
            ),
        ],
    )
    def test_department_input(self, input_value, expected_snippets):
        request_input = SearchDirectoryInput(department=input_value)
        queries = list(self.query_generator.generate(request_input))
        assert len(queries) == len(expected_snippets)
        for i, snippet in enumerate(expected_snippets):
            assert snippet in queries[i].description

    @pytest.mark.parametrize("authenticate", (True, False))
    def test_query_all_populations(self, authenticate: bool):
        """Ensures that, depending on the population and the authentication context,
        the correct queries are emitted.
        """
        if authenticate:
            self.session["uwnetid"] = "foo"
        request_input = SearchDirectoryInput(
            email="*whatever", population=PopulationType.all
        )
        queries = list(self.query_generator.generate(request_input))

        assert queries[0].request_input.employee_affiliation_state == "current"
        assert queries[0].request_input.student_affiliation_state is None
        if authenticate:
            assert queries[1].request_input.student_affiliation_state == "current"
            assert queries[1].request_input.employee_affiliation_state is None

    @pytest.mark.parametrize("authenticate", (True, False))
    def test_query_student_population(self, authenticate: bool):
        if authenticate:
            self.session["uwnetid"] = "foo"
        request_input = SearchDirectoryInput(
            email="*whatever", population=PopulationType.students
        )

        queries = list(self.query_generator.generate(request_input))
        if authenticate:
            assert len(queries) == 1
            assert queries[0].request_input.employee_affiliation_state is None
            assert queries[0].request_input.student_affiliation_state == "current"
        else:
            assert not queries
