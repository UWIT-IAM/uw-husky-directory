import os
import random
import re
import string
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, cast
from unittest import mock

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
    EmployeePosition,
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
def random_string():
    def inner(num_chars: int = 8) -> str:
        return "".join(random.choice(string.ascii_lowercase) for _ in range(8))

    return inner


@pytest.fixture
def generate_person(random_string):
    def inner(**attrs: Any) -> PersonOutput:
        netid = random_string()
        default = PersonOutput(
            display_name="Ada Lovelace",
            registered_name="Ada Lovelace",
            registered_surname="Lovelace",
            registered_first_middle_name="Ada",
            is_test_entity=False,
            netid=netid,
            href=f"person/{netid}",
            whitepages_publish=True,
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
                    mail_stop="351234",
                    directory_listing=EmployeeDirectoryListing(
                        publish_in_directory=True,
                        positions=[
                            EmployeePosition(
                                department="Aeronautics & Astronautics",
                                title="Senior Orbital Inclinator",
                            )
                        ],
                    ),
                )
            ),
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
                    directory_listing=StudentDirectoryListing(
                        publish_in_directory=True,
                        departments=["Quantum Physiology", "Transdimensional Studies"],
                        class_level="Senior",
                    )
                )
            )
        )

        contactable_person = generate_person(
            affiliations=PersonAffiliations(
                employee=EmployeePersonAffiliation(
                    mail_stop="351234",
                    directory_listing=EmployeeDirectoryListing(
                        publish_in_directory=True,
                        phones=["2068675309 Ext. 4242"],
                        pagers=["1234567"],
                        faxes=["+1 999 214-9864"],
                        mobiles=["+1 999 (967)-4222", "+1 999 (967) 4999"],
                        touch_dials=["+19999499911"],
                        emails=["dawg@uw.edu", "dawg2@uw.edu"],
                        voice_mails=["1800MYVOICE"],
                        positions=[
                            EmployeePosition(
                                department="Haute Cuisine", title="Garde Manger"
                            ),
                        ],
                    ),
                ),
                student=StudentPersonAffiliation(
                    directory_listing=StudentDirectoryListing(
                        publish_in_directory=True,
                        phone="19999674222",
                        email="student@uw.edu",
                        departments=["Cybertronic Engineering"],
                        class_level="Junior",
                    )
                ),
            )
        )

        @staticmethod
        def as_search_output(
            *people: PersonOutput, next_: Optional[str] = None
        ) -> Dict:
            result = ListPersonsOutput(
                persons=list(people),
                current=ListPersonsInput(),  # Not used
                page_size=len(people),
                page_start=1,
                total_count=len(people),
                next=next_,
            ).dict(by_alias=True)
            return result

        @property
        def published_student_employee(self) -> PersonOutput:
            published_student_employee = self.published_employee.copy()
            published_student_employee.affiliations.student = (
                self.published_student.affiliations.student
            )
            return published_student_employee

    return People()


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
                f"Could not find tag <{tag}> with args={args} and kwargs={kwargs}"
            )
        self._html = scope_
        try:
            yield scope_
        finally:
            self._html = parent_scope

    @property
    def html(self) -> Optional[BeautifulSoup]:
        return self._html

    def clean_bs4_text(self, text: str) -> str:
        """
        BeautifulSoup's text property preserves newlines
        from HTML indents. This makes it very  hard to search for matching
        text. So, this method does a passable job of cleaning up text to make
        it more parseable.

        This is heavily documented because it took a bit of
        tweaking to get right, and when dealing with tracking
        multiple indexes even I (@tomthorogood) get lost.

        Please expand this if you find more edge cases that block you.

        ----

        Example:

            <html>
                <b>
                    "Hello, fair knight,"
                </b> said the prince
                    ,
                who took a sip of
                    <a href="/wine">
                        wine
                    </a>.

        . . . would usually wind up looking something like this:

                "Hello fair knight,"
                said the prince
                ,
            who took a sip of
                    wine
                    .

        The output of this method is:
            "Hello fair knight," said the prince, who took a sip of wine.


        :param text: Text to clean up.
        :return: Cleaned up text. Read above.
        """
        # This is what will be used to create the result string
        # split() removes all whitespace, which is half the problem.
        sanitized = text.split()
        # The other half of the problem is that if punctuation
        # is on its own line, our resulting space-joined string would look like this:
        #   "Hello fair knight," said the prince , who took a sip of wine .

        # Tracks drift in the indexes for the sanitized words
        # vs. the not-quite sanitized copy.
        deletion_offset = 0
        # list(sanitized) creates a copy of the current state of sanitized,
        # which might include punctuation as separate items:
        #   [ . . . "the", "prince", ",", "who", . . . ]
        for index, word in enumerate(list(sanitized)):
            # Looks for punctuation-only "words"
            if index > 0 and not re.findall("[a-z0-9]", word):
                # The sanitized index is needed because every time
                # we perform this if-clause, we change the size
                # of `sanitized`, reducing it by 1 item.
                sanitized_index = index - deletion_offset
                # Our goal is to concatenate the punctuation into the
                # text of the previous word, so that "prince ," becomes
                # "prince,".
                preceding_word = sanitized[sanitized_index - 1]
                sanitized[sanitized_index - 1] = f"{preceding_word}{word}"

                # After we do this, we have to remove the offending
                # lone punctuation, otherwise we end up with
                #   "prince, ,"
                sanitized.pop(sanitized_index)

                # Finally, we increment the deletion offset
                # to make sure future iterations keep the two
                # models aligned.
                deletion_offset += 1
        return " ".join(sanitized)

    def has_tag_with_text(
        self, target_tag: str, search_text: str, assert_=False, assert_expected_=True
    ):
        """
        Searching substrings within elements is hard because of the way that BS4 parses HTML (i.e.,
        they include newlines that are in the HTML, but are not visible to the user.)

        This makes it easier by looping through all elements of a
        :param target_tag:
        :param search_text:
        :param assert_:
        :param assert_expected_:
        :return:
        """
        result = False
        search_text = search_text.lower()

        for element in self.html.find_all(target_tag):
            target_text = self.clean_bs4_text(element.text.lower())
            if search_text in target_text:
                result = True
                break

        if not assert_:
            return result

        if assert_expected_ != result:
            raise AssertionError(
                f"Expected {'not ' if not assert_expected_ else ''}"
                f"to find a <{target_tag}> tag with text including '{search_text}' in {self.html}"
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
            "label", attrs={"for": "population-option-students"}
        )
        all_populations = self.html.find(
            "label", attrs={"for": "population-option-all"}
        )
        result = bool(students_only and all_populations)
        if not assert_:
            return result
        if assert_expected_ != result:
            raise AssertionError(
                f"Expected student search options {'not ' if not assert_expected_ else ''}"
                f"to be visible."
            )

    def has_scenario_anchor(
        self, anchor_id: str, assert_=True, assert_expected_=True
    ) -> bool:
        """
        Validates that the html has both an an anchor _and_ a reference to the anchor.
        The anchor _must_ have the 'scenario-anchor' class, and any reference links must have the
        'scenario-anchor-reference' class.

        :param anchor_id: The id of the anchor to look for. If the population is "employees" and the scenario is
        "last name is 'foo'", then the anchor id is "employees-last-name-is-foo". See app.py#linkify
        """
        anchors = cast(
            List[BeautifulSoup], self.html.find_all(class_="scenario-anchor")
        )
        references = cast(
            List[BeautifulSoup],
            self.html.find_all("a", class_="scenario-anchor-reference"),
        )
        result = False
        for anchor in anchors:
            if anchor.attrs["id"] == anchor_id:
                for ref in references:
                    if ref.attrs["href"] == f"#{anchor_id}":
                        result = True
                        break  # exit for 'ref in references'
                break  # exit 'for anchor in anchors'
        if not assert_:
            return result
        if assert_expected_ != result:
            raise AssertionError(
                f"Expected to find an element with an id '{anchor_id}' as well as a link with 'href=#{anchor_id}'."
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


@pytest.fixture
def mocked_injections() -> Dict[Any, Any]:
    return {}


@pytest.fixture
def mock_injected(injector, mocked_injections):
    injector_get = injector.get

    def get_(cls):
        if cls in mocked_injections:
            return mocked_injections[cls]
        return injector_get(cls)

    @contextmanager
    def inner(cls, mocked_instance):
        mocked_injections[cls] = mocked_instance

        with mock.patch.object(injector, "get", get_):
            yield injector.get(cls)

    return inner
