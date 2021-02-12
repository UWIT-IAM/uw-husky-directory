from typing import Any, Dict, Union
from unittest import mock

import pytest

from husky_directory.models.pws import (
    ListPersonsInput,
    ListPersonsOutput,
)
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.search import DirectorySearchService


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

    @pytest.mark.parametrize(
        # In these parameters, the first argument must either be the name of a profile found in
        # the 'mock_people' fixture, OR a dictionary containing the `profile` key that mentions the base
        # profile, where all other attributes in the dict will override the default
        "profile, expected_result",
        [
            # A person with no affiliations should never be displayed.
            ("no_affiliations", False),
            # Test entities should never be displayed.
            ("test_entity", False),
            # This person has an employee affiliation and so should be allowed
            ("published_employee", True),
            # The top-level 'whitepages_publish' should invalidate the subsequent employee record that
            # has publish_in_directory=True.
            ({"profile": "published_employee", "whitepages_publish": False}, False),
            # This employee has elected not to be published, so should not be shown
            ("unpublished_employee", False),
            # This person is a student, and is not [currently] allowed in the listing, even though they are published
            ("published_student", False),
        ],
    )
    def test_filter_person(
        self, profile: Union[str, Dict[str, Any]], expected_result: bool
    ):
        if isinstance(profile, str):
            person = getattr(self.mock_people, profile)
        else:
            person = getattr(self.mock_people, profile["profile"])
            person = person.copy(update=profile)

        assert self.client._filter_person(person) is expected_result

    def test_search_directory_happy(self):
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)
        # The same data was returned a total of 10 times:

        assert output.num_results
        assert output.scenarios
        assert output.scenarios[0].people

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
        contacts = output.scenarios[0].people[0].phone_contacts

        for field_name, val in contacts:
            assert (
                getattr(
                    person.affiliations.employee.directory_listing, field_name, None
                )
                == val
            ), field_name
