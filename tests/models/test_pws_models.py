from husky_directory.models.pws import NamedIdentity, PersonOutput
from husky_directory.services.name_analyzer import NameAnalyzer


def test_name_analyzer():
    identity = NamedIdentity(
        display_name="ALOE VERA",
        registered_name="aloe VERA",
        registered_first_middle_name="Aloe A. Vera",
        registered_surname="VERA",
        preferred_first_name="Aloe",
        preferred_middle_name="A.",
        preferred_last_name="VERA",
    )
    analyzer = NameAnalyzer(identity)

    assert analyzer.normalized.display_name == "Aloe Vera"
    assert analyzer.identity.display_name == "ALOE VERA"
    assert analyzer.name_tokens == ["Aloe", "VERA"]
    assert analyzer.canonical_name_tokens == ["VERA", "Aloe"]
    assert analyzer.displayed_first_name == "Aloe"
    assert analyzer.displayed_surname == "VERA"
    assert analyzer.displayed_middle_name == ""
    assert analyzer.sort_key == "vera aloe"


def test_person_output_href():
    out = PersonOutput(
        registered_first_middle_name="Foo",
        registered_surname="Bar",
        display_name="Foo Bar",
        is_test_entity=False,
        whitepages_publish=True,
        regid="ABCDE123",
    )
    assert out.href == "/identity/v2/person/ABCDE123/full.json"
