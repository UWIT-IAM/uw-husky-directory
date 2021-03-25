import os
from contextlib import contextmanager
from typing import Any, Optional

import flask
import pytest
from bs4 import BeautifulSoup
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
    config.auth_settings.use_test_idp = True
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


class HTMLValidator:
    """
    This is an interface for BeautifulSoup that makes it a little
    easier to validate HTML state inside tests.

    validator = HTMLValidator()

    Every boolean helper method can be called as a boolean method, or as an assertion helper.
    Calling the boolean method (`has_blah`) as an assertion helper by prefixing it with `assert_`;
    likewise, call the negative assertion helper with `assert_not`.
    Examples:

       ```
        assert validator.has_foo()  # Boolean helpers start with 'has'
        validator.assert_has_foo()
        validator.assert_not_has_foo()
       ```

    with validator.validate_response(flask_client.get('/)) as html:
        html.find_all('p')  # Interact directly with the BS4 object, or
        assert validator.has_tag_with_text('p', 'foo')  # Call one of the boolean helpers, or
        validator.assert_has_tag_with_text('p', 'foo')  # Call an assertion helper, or
        validator.assert_not_has_tag_with_text('p', 'foo')


    If you want to scope in to an element (like a table, or complex div), you can use the .scope method to
    update the current validation scope:

    ```
        with validator.validate_response(flask_client.get('/data-table') as html:
            # Now both html and the validation helpers will be running all tests inside the table scope
            with validator.scope('table', id='my-crazy-data'):
                validator.assert_has_tag_with_text('td', '42')

            with validator.scope('table', id='my-sane-data):
                validator.assert_has_tag_with_text('td', '0')

    ```

    Adding boolean helpers:

    1. Name them something inquisitive, so they start with a predicate like "has" or "is".
    (Prefer a convention that uses "has",
    since we are always validating whether or not a DOM _has_ an element.

    2. They must accept the arguments `assert_=False, assert_expected_=True`;
    When `assert_` is true, then the validation will fail if the result does not match the assert_expected_ value.

    3. They must return a boolean.
    """

    def __init__(self):
        self._html: Optional[BeautifulSoup] = None

    def __getattr__(self, item: str):
        """
        Resonsible for mapping assertion helpers to the boolean operators, and
        setting up the callable context by populating the default args. This is all
        semantic sugar, and all of this could be done explicitly if desired.
        """
        test = None
        assert_expected = True
        if item.startswith("assert_not_"):
            test = item.split("_", maxsplit=2)[-1]
            assert_expected = False
        elif item.startswith("assert_"):
            test = item.split("_", maxsplit=1)[1]

        if not test or not hasattr(self, test):
            raise AttributeError(item)

        callable_ = getattr(self, test)

        def inner(*args, **kwargs):
            return callable_(
                *args, assert_=True, assert_expected_=assert_expected, **kwargs
            )

        return inner

    @contextmanager
    def scope(self, tag: str, *args, **kwargs):
        """Scopes in to the given tag parameters. Raises a ValueError if the tag does not exist."""
        parent_scope = self.html
        scope_ = self.html.find(tag, *args, **kwargs)
        if not scope_:
            raise ValueError(
                f"Could not find tag {tag} with args={args} and kwargs={kwargs}"
            )
        self._html = scope_
        try:
            yield scope_
        finally:
            self._html = parent_scope

    @property
    def html(self) -> Optional[BeautifulSoup]:
        return self._html

    def has_tag_with_text(
        self, tag: str, text: str, assert_=False, assert_expected_=True
    ):
        """
        Searching substrings within elements is hard because of the way that BS4 parses HTML (i.e.,
        they include newlines that are in the HTML, but are not visible to the user.)

        This makes it easier by looping through all elements of a
        :param tag:
        :param text:
        :param assert_:
        :param assert_expected_:
        :return:
        """
        result = False
        for element in self.html.find_all(tag):
            for word in text.split():
                if word not in element.text:
                    continue
            result = True

        if not assert_:
            return result

        if assert_expected_ != result:
            raise AssertionError(
                f"Expected {'not ' if not assert_expected_ else ''}"
                f"to find tags with text matching {text}"
            )
        return False

    def has_sign_in_link(self, assert_=False, assert_expected_=True) -> bool:
        result = bool(self.html.find("a", id="sign-in"))
        if not assert_:
            return result
        if assert_expected_ != result:
            raise AssertionError(
                f"Expected sign-in link {'not ' if not assert_expected_ else '' }to be found."
            )

    def has_student_search_options(self, assert_=True, assert_expected_=True) -> bool:
        students_only = self.html.find(
            "label", attrs={"for": "student-population-option"}
        )
        all_populations = self.html.find(
            "label", attrs={"for": "all-populations-option"}
        )
        result = bool(students_only and all_populations)
        if not assert_:
            return result
        if assert_expected_ != result:
            raise AssertionError(
                f"Expected student search options {'not ' if not assert_expected_ else ''}"
                f"to be visible."
            )

    @contextmanager
    def validate_response(self, response: flask.Response) -> BeautifulSoup:
        """
        Creates a context for a given flask response, and creates a BS4 instance for validation.
        Unless `scope` is called, all validations will be run with the full page data as the
        context; you can use scope() to zoom in to certain container elements and run validations
        only inside that scope.
        """
        self._html = BeautifulSoup(response.data, "html.parser")
        try:
            yield self._html
        finally:
            self._html = None


@pytest.fixture(scope="session")
def html_validator() -> HTMLValidator:
    return HTMLValidator()
