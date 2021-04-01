from typing import Any, Dict, List, Union
from unittest import mock

import pytest
from werkzeug.local import LocalProxy

from husky_directory.models.pws import (
    ListPersonsInput,
    ListPersonsOutput,
)
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.search import (
    DirectorySearchService,
    ListPersonsOutputTranslator,
    PersonOutputFilter,
)


class TestDirectorySearchService:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector, mock_people):
        self.mock_people = mock_people
        self.client: DirectorySearchService = injector.get(DirectorySearchService)
        self.pws: PersonWebServiceClient = injector.get(PersonWebServiceClient)

        self.mock_list_persons = mock.patch.object(self.pws, "list_persons").start()
        self.mock_get_next = mock.patch.object(self.pws, "get_next").start()

        self.set_list_persons_output(
            mock_people.as_search_output(mock_people.published_employee)
        )

    def set_list_persons_output(self, output: ListPersonsOutput):
        self.list_persons_output = output
        self.mock_list_persons.return_value = output

    def set_get_next_output(self, output: ListPersonsOutput):
        self.get_next_output = output
        self.mock_get_next.return_value = output

    def test_search_directory_happy(self):
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)
        # The same data was returned a total of 10 times:

        assert output.num_results
        assert output.scenarios
        assert output.scenarios[0].populations["employees"].people

    def test_search_removes_duplicates(self):
        dupe = self.mock_people.as_search_output(self.mock_people.published_employee)
        self.set_list_persons_output(
            dupe.copy(update={"next": ListPersonsInput(href="foo")})
        )
        self.set_get_next_output(dupe)
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)

        # But we should only expect a single result because it was de-duplicated
        assert output.num_results == 1

    def test_output_includes_phones(self):
        person = self.mock_people.contactable_person
        self.list_persons_output.persons = [person]
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)
        contacts = output.scenarios[0].populations["employees"].people[0].phone_contacts

        for field_name, val in contacts:
            assert (
                getattr(
                    person.affiliations.employee.directory_listing, field_name, None
                )
                == val
            ), field_name


class TestPersonOutputTranslator:
    @pytest.fixture(autouse=True)
    def initialize(self, injector, mock_people):
        self.injector = injector
        self.mock_people = mock_people

    @property
    def translator(self) -> ListPersonsOutputTranslator:
        return self.injector.get(ListPersonsOutputTranslator)

    def mock_authentication(self):
        orig_get = self.injector.get

        def _get(class_):
            if class_ == LocalProxy:
                return {"uwnetid": "authuser"}
            return orig_get(class_)

        patch = mock.patch.object(self.injector, "get").start()
        patch.side_effect = _get

    @pytest.mark.parametrize("should_be_authed", (True, False))
    def test_current_request_is_authenticated(self, should_be_authed):
        if should_be_authed:
            self.mock_authentication()
        assert self.translator.current_request_is_authenticated == should_be_authed

    @pytest.mark.parametrize(
        # In these parameters, the first argument must either be the name of a profile found in
        # the 'mock_people' fixture, OR a dictionary containing the `profile` key that mentions the base
        # profile, where all other attributes in the dict will override the default
        "profile, allowed_populations, request_is_authenticated, expected_result",
        [
            # A person with no affiliations should never be displayed.
            ("no_affiliations", ["employees", "students"], True, False),
            # TODO: Update once test entities are supported fully
            ("test_entity", ["employees"], False, False),
            # Every day published employee should:
            #   - Be visible regardless of auth
            ("published_employee", ["employees"], False, True),
            ("published_employee", ["employees"], True, True),
            #   - Be included any time "employees" is an allowed population
            ("published_employee", ["employees", "students"], False, True),
            #   - Not be visible when only "students" are selected
            ("published_employee", ["students"], True, False),
            # The top-level 'whitepages_publish' should invalidate the subsequent employee record that
            # has publish_in_directory=True.
            (
                {"profile": "published_employee", "whitepages_publish": False},
                ["employees"],
                False,
                False,
            ),
            # This employee has elected not to be published, so should not be shown
            ("unpublished_employee", ["employees"], False, False),
            # Student affiliations should only be returned if the user is authenticated and opted to see
            # student data
            #   - Regardless of auth students should never be returned if user has not requested them
            ("published_student", ["employees"], False, False),
            ("published_student", ["employees"], True, False),
            #   - Even if requested, without auth, student data should be returned
            ("published_student", ["employees", "students"], False, False),
            #   - Only if requested AND authed can student data be returned
            ("published_student", ["students"], True, True),
        ],
    )
    def test_filter_person(
        self,
        profile: Union[str, Dict[str, Any]],
        allowed_populations: List[str],
        request_is_authenticated: bool,
        expected_result: bool,
    ):
        if request_is_authenticated:
            self.mock_authentication()

        if isinstance(profile, str):
            person = getattr(self.mock_people, profile)
        else:
            person = getattr(self.mock_people, profile["profile"])
            person = person.copy(update=profile)

        assert (
            self.translator.filter_person(
                person, PersonOutputFilter(allowed_populations=allowed_populations)
            )
            == expected_result
        )
