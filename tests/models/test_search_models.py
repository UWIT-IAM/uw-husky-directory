import pytest
from pydantic import ValidationError

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


@pytest.mark.parametrize(
    "query_value, expected_value",
    [
        ("foo\\", "foo"),
        ("f\\oo\\", "foo"),
    ],
)
def test_form_input_strips_illegal_chars(query_value, expected_value):
    form_input = SearchDirectoryFormInput(query=query_value)
    assert form_input.query == expected_value
