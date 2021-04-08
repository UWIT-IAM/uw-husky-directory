from husky_directory.models.pws import PersonOutput


def test_person_output_href():
    out = PersonOutput(
        display_name="Foo Bar",
        is_test_entity=False,
        whitepages_publish=True,
        regid="ABCDE123",
    )
    assert out.href == "/identity/v2/person/ABCDE123/full.json"
