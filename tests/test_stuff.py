import os

import pytest

from husky_directory.models.pws import ListPersonsOutput


@pytest.fixture
def sample_data():
    filename = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "listing.json"
    )
    with open(filename) as f:
        return f.read()


def test_parse_pws_output(sample_data):
    """This is a bad test that ensures we can use our data models to load sample data
    from PWS. It's bad because the data is static; what we really need is an
    integration test that just queries PWS to validate results, but that'll come
    later. This is just as a preliminary safeguard."""
    assert ListPersonsOutput.parse_raw(sample_data)
