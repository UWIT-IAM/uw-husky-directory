from typing import Any
from unittest import mock

import pytest

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
                directory_listing=EmployeeDirectoryListing(publish_in_directory=True)
            )
        )
    )
    unpublished_employee = generate_person(
        affiliations=PersonAffiliations(
            employee=EmployeePersonAffiliation(
                directory_listing=EmployeeDirectoryListing(publish_in_directory=False)
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
                )
            )
        )
    )


class TestDirectorySearchService:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector, mock_person_data):
        self.client: DirectorySearchService = injector.get(DirectorySearchService)
        self.pws: PersonWebServiceClient = injector.get(PersonWebServiceClient)

        self.mock_list_persons = mock.patch.object(self.pws, "list_persons").start()
        self.mock_get_next = mock.patch.object(self.pws, "get_next").start()

        self.set_list_persons_output(ListPersonsOutput.parse_obj(mock_person_data))
        del mock_person_data["Next"]
        self.set_get_next_output(ListPersonsOutput.parse_obj(mock_person_data))

    def set_list_persons_output(self, output: ListPersonsOutput):
        self.list_persons_output = output
        self.mock_list_persons.return_value = output

    def set_get_next_output(self, output: ListPersonsOutput):
        self.get_next_output = output
        self.mock_get_next.return_value = output

    @pytest.mark.parametrize(
        "person, expected_result",
        [
            # A person with no affiliations should never be displayed.
            (People.no_affiliations, False),
            # Test entities should never be displayed.
            (People.test_entity, False),
            # This person has an employee affiliation and so should be allowed
            (People.published_employee, True),
            # The top-level 'whitepages_publish' should invalidate the subsequent employee record that
            # has publish_in_directory=True.
            (
                People.published_employee.copy(update={"whitepages_publish": False}),
                False,
            ),
            # This employee has elected not to be published, so should not be shown
            (People.unpublished_employee, False),
            # This person is a student, and is not [currently] allowed in the listing, even though they are published
            (People.published_student, False),
        ],
    )
    def test_filter_person(self, person: PersonOutput, expected_result: bool):
        assert self.client._filter_person(person) is expected_result

    def test_search_directory_happy(self):
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)
        # The same data was returned a total of 10 times:

        assert output.query.name == "foo"
        assert output.num_results
        assert output.scenarios
        assert output.scenarios[0].people

    def test_search_removes_duplicates(self):
        dupe = ListPersonsOutput(
            persons=[People.published_employee],
            current=ListPersonsInput(),
            page_size=1,
            page_start=1,
            total_count=1,
        )
        self.set_list_persons_output(dupe)
        self.set_get_next_output(dupe)
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)

        # But we should only expect a single result because it was de-duplicated
        assert output.num_results == 1

    def test_output_includes_phones(self):
        person = People.contactable_person
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

    def test_output_includes_original_phone_query(self):
        request_input = SearchDirectoryInput(phone="abcdef")
        output = self.client.search_directory(request_input)
        assert request_input.sanitized_phone == ""
        assert output.query.phone == "abcdef"
