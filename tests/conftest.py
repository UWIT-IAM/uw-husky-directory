import json
import os
from typing import Dict

import pytest
from flask import Flask
from injector import Injector

from husky_directory.app import create_app, create_app_injector


@pytest.fixture(scope="session")
def test_root_path() -> str:
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="session")
def test_data_path(test_root_path) -> str:
    return os.path.join(test_root_path, "data")


@pytest.fixture
def injector() -> Injector:
    return create_app_injector()


@pytest.fixture(autouse=True)
def app(injector) -> Flask:
    return create_app(injector)


@pytest.fixture
def mock_person_data(test_data_path) -> Dict:
    with open(os.path.join(test_data_path, "listing.json")) as f:
        return json.loads(f.read())
