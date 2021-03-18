import os
from typing import Any, Optional

import pytest
from flask import Flask
from injector import Injector

from husky_directory.app import create_app, create_app_injector
from husky_directory.app_config import ApplicationConfig
from husky_directory.models.pws import (
    EmployeeDirectoryListing,
    EmployeePersonAffiliation,
    ListPersonsInput,
    ListPersonsOutput,
    PersonAffiliations,
    PersonOutput,
    StudentDirectoryListing,
    StudentPersonAffiliation,
)


@pytest.fixture(scope="session")
def test_root_path() -> str:
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="session")
def test_data_path(test_root_path) -> str:
    return os.path.join(test_root_path, "data")


@pytest.fixture
def injector() -> Injector:
    return create_app_injector()


@pytest.fixture
def app_config(injector) -> ApplicationConfig:
    config = injector.get(ApplicationConfig)
    config.use_test_idp = True
    return config


@pytest.fixture(autouse=True)
def app(
    injector,
    app_config,  # ensures app_config fixture loads before the Flask app.
) -> Flask:
    return create_app(injector)


@pytest.fixture
def generate_person():
    def inner(**attrs: Any) -> PersonOutput:
        default = PersonOutput(
            display_name="Ada Lovelace",
            registered_name="Ada Lovelace",
            registered_surname="Lovelace",
            registered_first_middle_name="Ada",
            whitepages_publish=True,
            is_test_entity=False,
            netid="ada",
        )
        return default.copy(update=attrs)

    return inner


@pytest.fixture
def mock_people(generate_person):
    class People:
        """
        A repository for handy people. Good for things that are common cases; for highly specialized
        cases, it's probably better to just declare them in situ.
        """

        no_affiliations = generate_person()
        test_entity = generate_person(is_test_entity=True)
        published_employee = generate_person(
            affiliations=PersonAffiliations(
                employee=EmployeePersonAffiliation(
                    directory_listing=EmployeeDirectoryListing(
                        publish_in_directory=True
                    )
                )
            )
        )
        unpublished_employee = generate_person(
            affiliations=PersonAffiliations(
                employee=EmployeePersonAffiliation(
                    directory_listing=EmployeeDirectoryListing(
                        publish_in_directory=False
                    )
                )
            )
        )
        published_student = generate_person(
            affiliations=PersonAffiliations(
                student=StudentPersonAffiliation(
                    directory_listing=StudentDirectoryListing(publish_in_directory=True)
                )
            )
        )
        contactable_person = generate_person(
            affiliations=PersonAffiliations(
                employee=EmployeePersonAffiliation(
                    directory_listing=EmployeeDirectoryListing(
                        publish_in_directory=True,
                        phones=["2068675309 Ext. 4242"],
                        pagers=["1234567"],
                        faxes=["+1 999 214-9864"],
                        mobiles=["+1 999 (967)-4222", "+1 999 (967) 4999"],
                        touch_dials=["+19999499911"],
                        emails=["dawg@uw.edu"],
                    )
                )
            )
        )

        @staticmethod
        def as_search_output(
            *people: PersonOutput, next_: Optional[str] = None
        ) -> ListPersonsOutput:
            return ListPersonsOutput(
                persons=list(people),
                current=ListPersonsInput(),  # Not used
                page_size=len(people),
                page_start=1,
                total_count=len(people),
                next=next_,
            )

    return People
