from typing import Any
from unittest import mock

import pytest

from husky_directory.models.pws import (
    EmployeeDirectoryListing,
    EmployeePersonAffiliation,
    ListPersonsOutput,
    PersonAffiliations,
    PersonOutput,
    StudentDirectoryListing,
    StudentPersonAffiliation,
)
from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.search import DirectorySearchService


def generate_person(**attrs: Any) -> PersonOutput:
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


class TestDirectorySearchService:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector, mock_person_data):
        self.client: DirectorySearchService = injector.get(DirectorySearchService)
        self.pws: PersonWebServiceClient = injector.get(PersonWebServiceClient)
        self.list_persons_output = ListPersonsOutput.parse_obj(mock_person_data)
        del mock_person_data["Next"]
        self.get_next_output = ListPersonsOutput.parse_obj(mock_person_data)

        mock_list_persons = mock.patch.object(self.pws, "list_persons").start()
        mock_get_next = mock.patch.object(self.pws, "get_next").start()

        mock_list_persons.return_value = self.list_persons_output
        mock_get_next.return_value = self.get_next_output

    @pytest.mark.parametrize(
        "person, expected_result",
        [
            (
                generate_person(),
                False,
            ),  # Default has no affiliations, so is not eligible,
            # Test entities should always be filtered
            (generate_person(is_test_entity=True), False),
            # This person has an employee affiliation and so should be allowed
            (
                generate_person(
                    affiliations=PersonAffiliations(
                        employee=EmployeePersonAffiliation(
                            directory_listing=EmployeeDirectoryListing(
                                publish_in_directory=True
                            )
                        )
                    )
                ),
                True,
            ),
            # This person is an employee, but has elected not to be published.
            (
                generate_person(
                    affiliations=PersonAffiliations(
                        employee=EmployeePersonAffiliation(
                            directory_listing=EmployeeDirectoryListing(
                                publish_in_directory=False
                            )
                        )
                    )
                ),
                False,
            ),
            # This person is a student, and is not [currently] allowed in the listing
            (
                generate_person(
                    affiliations=PersonAffiliations(
                        student=StudentPersonAffiliation(
                            directory_listing=StudentDirectoryListing(
                                publish_in_directory=True
                            )
                        )
                    )
                ),
                False,
            ),
            # The top-level 'whitepages_publish' should invalidate the subsequent employee record that
            # has publish_in_directory=True.
            (
                generate_person(
                    whitepages_publish=False,
                    affiliations=PersonAffiliations(
                        employee=EmployeePersonAffiliation(
                            directory_listing=EmployeeDirectoryListing(
                                publish_in_directory=True
                            )
                        )
                    ),
                ),
                False,
            ),
        ],
    )
    def test_filter_person(self, person: PersonOutput, expected_result: bool):
        assert self.client._filter_person(person) is expected_result

    def test_search_directory(self):
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)
        assert output.query.name == "foo"
        assert output.num_results
        assert output.scenarios
        assert output.scenarios[0].people
