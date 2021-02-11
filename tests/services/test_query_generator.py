from typing import Dict, Optional

import pytest
from injector import Injector

from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.query_generator import (
    Query,
    QueryTemplate,
    SearchQueryGenerator,
    WildcardFormat,
)


class TestQueryTemplate:
    @pytest.fixture(autouse=True)
    def initialize(self):
        self.template = QueryTemplate(
            description_fmt='First name "{}", last name "{}"',
            query_generator=lambda first, last: Query(first_name=first, last_name=last),
        )
        self.args = ["Bill", "Waterson"]

    def test_get_query(self):
        query = self.template.get_query(self.args)
        assert query.first_name == "Bill"
        assert query.last_name == "Waterson"

    def test_get_description(self):
        description = self.template.get_description(self.args)
        assert description == 'First name "Bill", last name "Waterson"'

    def test_description_formatter(self):
        self.template.description_formatter = lambda first, last: (
            " ".join([first, last]),
        )
        self.template.description_fmt = 'Name "{}"'
        description = self.template.get_description(self.args)
        assert description == 'Name "Bill Waterson"'


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
    def initialize(self, injector: Injector):
        self.injector = injector
        self.query_generator = injector.get(SearchQueryGenerator)

    def test_wildcard_input(self):
        generated = list(
            self.query_generator.generate(SearchDirectoryInput(name="foo*"))
        )
        assert len(generated) == 1
        print(generated)
        description, query = generated[0]
        assert description == 'Name matches "foo*"'

    def test_single_name_input(self):
        generated = list(
            self.query_generator.generate(SearchDirectoryInput(name="foo"))
        )
        assert len(generated) == 5  # 1 global query, 4 from query_templates[1]
        expected_queries = [
            dict(display_name="foo"),
            dict(last_name="foo"),
            dict(last_name="foo*"),
            dict(first_name="foo"),
            dict(display_name="*foo*"),
        ]
        actual_queries = [
            query.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
            for desc, query in generated
        ]
        assert expected_queries == actual_queries

    def test_two_name_input(self):
        generated = list(
            self.query_generator.generate(SearchDirectoryInput(name="foo bar"))
        )
        assert len(generated) == 6  # 1 global query, 5 fro query_templates[2]
        expected_queries = [
            dict(display_name="foo bar"),
            dict(first_name="foo", last_name="bar"),
            dict(first_name="foo*", last_name="bar"),
            dict(first_name="foo", last_name="bar*"),
            dict(first_name="foo*", last_name="bar*"),
            dict(last_name="foo bar*"),
        ]
        actual_queries = [
            query.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
            for desc, query in generated
        ]
        assert expected_queries == actual_queries

    @pytest.mark.parametrize(
        "request_input, expected_num_queries, assert_included",
        [
            (
                "foo bar baz",
                10,
                [
                    dict(display_name="foo bar baz"),
                    dict(display_name="foo* bar* baz*"),
                    dict(first_name="foo", last_name="bar baz"),
                    dict(first_name="foo", last_name="bar baz*"),
                    dict(first_name="foo*", last_name="bar baz"),
                    dict(first_name="foo*", last_name="bar baz*"),
                    dict(first_name="foo bar", last_name="baz"),
                    dict(first_name="foo bar", last_name="baz*"),
                    dict(first_name="foo bar*", last_name="baz"),
                    dict(first_name="foo bar*", last_name="baz*"),
                ],
            ),
            # Skipping the detailed tests for the cardinalities, because that's a whole lot of typing. Just checking
            # a couple of cases to verify that the slicing is being handled as expected.
            (
                "foo bar baz bop",
                14,
                [
                    dict(first_name="foo", last_name="bar baz bop"),
                    dict(first_name="foo bar", last_name="baz bop"),
                    dict(first_name="foo bar baz", last_name="bop"),
                ],
            ),
            ("foo bar baz bop blop", 18, None),
        ],
    )
    def test_multi_name_input_generation(
        self,
        request_input: str,
        expected_num_queries: int,
        assert_included: Optional[Dict[str, str]],
    ):
        generated = list(
            self.query_generator.generate(SearchDirectoryInput(name=request_input))
        )
        if assert_included:
            actual_queries = [
                query.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
                for desc, query in generated
            ]
            for case in assert_included:
                assert case in actual_queries

        assert len(generated) == expected_num_queries

    def test_phone_input_short_number(self):
        request_input = SearchDirectoryInput(phone="2065554321")
        queries = list(self.query_generator.generate(request_input))
        assert len(queries) == 1

    def test_phone_input_long_number(self):
        request_input = SearchDirectoryInput(phone="+1 (206) 555-4321")
        queries = list(self.query_generator.generate(request_input))
        assert queries[0][1].phone_number == "12065554321"
        assert queries[1][1].phone_number == "2065554321"
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
        assert queries[0][1].mail_stop == "123456"
        assert queries[1][1].mail_stop == "35123456"
