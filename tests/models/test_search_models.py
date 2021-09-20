import pytest
from pydantic import ValidationError

from husky_directory.models.enum import PopulationType
from husky_directory.models.search import SearchDirectoryFormInput, SearchDirectoryInput


class TestSearchDirectoryInput:
    def test_search_methods(self):
        assert SearchDirectoryInput.search_methods() == [
            # Yes, this does mean we need to manually update the test if
            # these fields ever change in any way. This prevents us from
            # unintended changes that may impact the user experience.
            "name",
            "department",
            "email",
            "box_number",
            "phone",
        ]

    def test_sanitized_phone(self):
        assert (
            SearchDirectoryInput(phone="+1 (555) 867-5309").sanitized_phone
            == "15558675309"
        )

    @pytest.mark.parametrize("box_number", ["1234567", "12345A"])
    def test_validate_box_number_invalid(self, box_number: str):
        with pytest.raises(ValidationError):
            SearchDirectoryInput(box_number=box_number)

    @pytest.mark.parametrize("box_number", ["123456", "", None])
    def test_validate_box_number_valid(self, box_number: str):
        assert SearchDirectoryInput(box_number=box_number).box_number == box_number

    @pytest.mark.parametrize("email", ("foo", "foo@uw", "foo@uw.edu"))
    def test_validate_email_success(self, email):
        assert SearchDirectoryInput(email=email).email == email  # email?

    @pytest.mark.parametrize("email", ("@uw", "@uw.edu"))
    def test_validate_email_failure(self, email):
        with pytest.raises(ValidationError):
            SearchDirectoryInput(email="@uw")

    @pytest.mark.parametrize(
        "input_population, expected",
        [
            ("employees", ["employees"]),
            ("students", ["students"]),
            ("all", ["employees", "students"]),
        ],
    )
    def test_requested_populations(self, input_population, expected):
        assert (
            SearchDirectoryInput(population=input_population).requested_populations
            == expected
        )


class TestSearchDirectoryFormInput:
    @pytest.mark.parametrize(
        "render_population, expected",
        [
            (None, PopulationType.employees),
            (PopulationType.students, PopulationType.students),
        ],
    )
    def test_population_default(self, render_population, expected):
        form_input = SearchDirectoryFormInput(render_population=render_population)
        assert PopulationType(form_input.render_population) == PopulationType(expected)


@pytest.mark.parametrize(
    "query_value, expected_value",
    [
        # Ensure illegal characters explicitly stripped
        ("f\\oo\\", "foo"),
        # Ensure leading/trailing whitespace is
        # automatically stripped by pydantic
        ("\tfoo\t", "foo"),
        ("  foo bar  ", "foo bar"),
        # Ensure tab characters are converted to spacees
        ("foo\tbar", "foo bar"),
        # Ensure multiple spaces are condensed to a single spacee
        ("foo     bar", "foo bar"),
        # Ensure all the things
        ("  foo\t   \t  bar    \t", "foo bar"),
    ],
)
def test_form_input_strips_illegal_chars(query_value, expected_value):
    form_input = SearchDirectoryFormInput(query=query_value)
    assert form_input.query == expected_value


@pytest.mark.parametrize(
    "query, method, is_valid",
    [
        ("", "name", False),
        ("hi", "name", True),
        ("hi", "department", False),
        ("h", "name", False),
    ],
)
def test_form_input_validation(query, method, is_valid):
    try:
        SearchDirectoryFormInput(query=query, method=method)
    except ValidationError:
        assert not is_valid
