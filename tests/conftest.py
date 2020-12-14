import pytest

from husky_directory.app import create_app


@pytest.fixture
def app():
    return create_app()
