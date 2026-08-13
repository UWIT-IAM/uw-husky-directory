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


def test_name_analyzer_registered_surname_only():
    """
    Identities that have not set a preferred name still have their
    registered surname available to us, so we must use it to find
    surnames that are made up of more than one word.
    """
    identity = NamedIdentity(
        display_name="Jane Van Der Berg",
        registered_name="Jane Van Der Berg",
        registered_first_middle_name="Jane",
        registered_surname="Van Der Berg",
    )
    analyzer = NameAnalyzer(identity)

    assert analyzer.normalized.registered_surname == "Van Der Berg"
    assert analyzer.displayed_surname == "Van Der Berg"
    assert analyzer.displayed_first_name == "Jane"
    assert analyzer.displayed_middle_name == ""
    assert analyzer.name_tokens == ["Jane", "Van Der Berg"]
    assert analyzer.canonical_name_tokens == ["Van Der Berg", "Jane"]
    assert analyzer.sort_key == "van der berg jane"


def test_name_analyzer_registered_first_middle_name():
    """
    Registered names combine the first and middle names, so both are
    displayed as the first name; the surname must not be included, and
    neither should the space that separated them.
    """
    identity = NamedIdentity(
        display_name="Jane Q Public",
        registered_name="Jane Q Public",
        registered_first_middle_name="Jane Q",
        registered_surname="Public",
    )
    analyzer = NameAnalyzer(identity)

    assert analyzer.displayed_first_name == "Jane Q"
    assert analyzer.displayed_surname == "Public"
    assert analyzer.name_tokens == ["Jane Q", "Public"]
    assert analyzer.sort_key == "public jane q"


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
