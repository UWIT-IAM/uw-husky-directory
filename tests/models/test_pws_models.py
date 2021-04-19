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
