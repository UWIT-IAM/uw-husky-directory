import pytest

from husky_directory.models.pws import NamedIdentity, PersonOutput


def test_name_formatting():
    identity = NamedIdentity(
        display_name="ALOE VERA",
        registered_name="aloe VERA",
        registered_first_middle_name="Aloe A. Vera",
        registered_surname="VERA",
        preferred_first_name="Aloe",
        preferred_middle_name="A.",
        preferred_last_name="VERA",
    )

    expected = {
        "display_name": "Aloe Vera",
        "registered_name": "Aloe Vera",
        "registered_first_middle_name": "Aloe A. Vera",
        "registered_surname": "Vera",
        "preferred_first_name": "Aloe",
        "preferred_middle_name": "A.",
        "preferred_last_name": "Vera",
    }
    assert identity.dict() == expected


def test_person_output_href():
    out = PersonOutput(
        display_name="Foo Bar",
        is_test_entity=False,
        whitepages_publish=True,
        regid="ABCDE123",
    )
    assert out.href == "/identity/v2/person/ABCDE123/full.json"


@pytest.mark.parametrize(
    "model, expected",
    [
        (
            NamedIdentity(registered_surname="smith", display_name="j h roberts"),
            "Roberts",
        ),
        (
            NamedIdentity(registered_surname="smith", display_name="j h finney-smith"),
            "Finney-smith",
        ),
        # This is an unlikely case where a person has a display_name that differs from their registered_name, but
        # they haven't set a preferred_name. I'm not sure if this is even possible, but if it ever happens, we'll
        # elect to honor the registered_surname as long as it is a token in the user's display name.
        (
            NamedIdentity(registered_surname="smith", display_name="j smith hannaford"),
            "Smith",
        ),
        (
            NamedIdentity(
                registered_surname="smith",
                preferred_last_name="hannaford",
                display_name="j smith hannaford",
            ),
            "Hannaford",
        ),
        (NamedIdentity(registered_surname="smith", display_name="j h smith"), "Smith"),
    ],
)
def test_get_displayed_surname(model: NamedIdentity, expected):
    assert model.get_displayed_surname() == expected
