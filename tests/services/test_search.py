from contextlib import ExitStack
from typing import Dict
from unittest import mock

import pytest
from werkzeug.local import LocalProxy

from husky_directory.models.common import UWDepartmentRole
from husky_directory.models.enum import PopulationType
from husky_directory.models.pws import (
    ListPersonsOutput,
)
from husky_directory.models.search import Person, SearchDirectoryInput
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.search import (
    DirectorySearchService,
)


class TestDirectorySearchService:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector, mock_people, mock_injected):
        self.mock_people = mock_people
        self.session = {}

        # We have to mock a lot here in order to avoid replicating
        # an entire mock backend. The ExitStack allows us to add
        # several layers of nested contexts without having to indent
        # each time. Essentially, here, the stack just flattens
        # out the view of our nest.
        #
        # TODO: This _does_ smell like too many mocks, but another
        #       refactor seems like a "down the road" thing.
        with ExitStack() as stack:
            stack.enter_context(mock_injected(LocalProxy, self.session))
            self.pws = injector.get(PersonWebServiceClient)
            stack.enter_context(mock_injected(PersonWebServiceClient, self.pws))
            self.mock_list_persons = stack.enter_context(
                mock.patch.object(self.pws, "_get_search_request_output")
            )
            self.mock_get_explicit_href = stack.enter_context(
                mock.patch.object(self.pws, "get_explicit_href")
            )

            self.set_list_persons_output(
                mock_people.as_search_output(mock_people.published_employee)
            )
            self.client: DirectorySearchService = injector.get(DirectorySearchService)
            yield

    def set_list_persons_output(self, output: Dict):
        self.list_persons_output = output
        self.mock_list_persons.return_value = output

    def set_get_next_output(self, output: ListPersonsOutput):
        self.get_next_output = output
        self.mock_get_explicit_href.return_value = output

    def test_search_directory_happy(self):
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)

        assert output.num_results
        assert output.scenarios
        assert output.scenarios[0].populations["employees"].people

    def test_search_removes_duplicates(self):
        orig = self.mock_people.as_search_output(self.mock_people.published_employee)
        dupe = orig.copy()
        orig["Next"] = {"Href": "foo"}
        self.set_list_persons_output(orig)
        self.set_get_next_output(ListPersonsOutput.parse_obj(dupe))
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)

        # But we should only expect a single result because it was de-duplicated
        assert output.num_results == 1

    def test_output_includes_phones(self):
        person = self.mock_people.contactable_person
        self.list_persons_output["Persons"] = [person.dict(by_alias=True)]
        self.session["uwnetid"] = "foo"
        request_input = SearchDirectoryInput(name="foo")
        output = self.client.search_directory(request_input)
        contacts = output.scenarios[0].populations["employees"].people[0].phone_contacts

        assert contacts == dict(
            phones=["2068675309 Ext. 4242", "19999674222"],
            faxes=["+1 999 214-9864"],
            voice_mails=["1800MYVOICE"],
            touch_dials=["+19999499911"],
            mobiles=["+1 999 (967)-4222", "+1 999 (967) 4999"],
            pagers=["1234567"],
        )

    @pytest.mark.parametrize(
        "person, expected_departments",
        [
            (
                "published_employee",
                [
                    # We could easily automate this lookup,
                    # but then we'd never know if something unexpected changes.
                    # (Note to future self.)
                    # See conftest::mock_people::published_employee
                    UWDepartmentRole(
                        department="Aeronautics & Astronautics",
                        title="Senior Orbital Inclinator",
                    )
                ],
            ),
            (
                "published_student",
                [
                    # See conftest::mock_people::publisehd_student
                    UWDepartmentRole(
                        department="Quantum Physiology",
                        title="Senior",
                    ),
                    UWDepartmentRole(
                        department="Transdimensional Studies",
                        title="Senior",
                    ),
                ],
            ),
            (
                "published_student_employee",
                [
                    # See conftest::mock_people::publisehd_student
                    UWDepartmentRole(
                        department="Quantum Physiology",
                        title="Senior",
                    ),
                    UWDepartmentRole(
                        department="Transdimensional Studies",
                        title="Senior",
                    ),
                    UWDepartmentRole(
                        department="Aeronautics & Astronautics",
                        title="Senior Orbital Inclinator",
                    ),
                ],
            ),
        ],
    )
    def test_output_includes_department(self, person: str, expected_departments):
        self.session["uwnetid"] = "foo"
        input_population = None
        expected_populations = []

        if "student" in person:
            input_population = PopulationType.students
            expected_populations.append(input_population)

        if "employee" in person:
            if input_population:
                input_population = PopulationType.all
            else:
                input_population = PopulationType.employees
            expected_populations.append(PopulationType.employees)

        input_population = PopulationType(input_population)
        person = getattr(self.mock_people, person)
        self.list_persons_output["Persons"] = [person.dict(by_alias=True)]
        request_input = SearchDirectoryInput(
            name="Lovelace", population=input_population
        )
        output = self.client.search_directory(request_input)
        assert output.scenarios, output.dict()
        for population in expected_populations:
            assert (
                output.scenarios[0].populations[population.value].people[0].departments
                == expected_departments
            )

    def test_department_ignores_invalid_data(self):
        person = self.mock_people.published_employee
        person.affiliations.employee.directory_listing.positions[0].department = None
        self.list_persons_output["Persons"] = [person.dict(by_alias=True)]
        request_input = SearchDirectoryInput(
            name="whatever", population=PopulationType.employees
        )
        output = self.client.search_directory(request_input)
        output_person: Person = output.scenarios[0].populations["employees"].people[0]
        assert not output_person.departments

    def test_output_includes_box_number(self):
        person = self.mock_people.published_employee
        self.list_persons_output["Persons"] = [person.dict(by_alias=True)]
        output = self.client.search_directory(
            SearchDirectoryInput(name="*blah", population=PopulationType.employees)
        )
        output_person: Person = output.scenarios[0].populations["employees"].people[0]
        assert output_person.box_number == "351234"
