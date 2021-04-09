from contextlib import ExitStack
from typing import Any, Dict, List, Union
from unittest import mock

import pytest
from werkzeug.local import LocalProxy

from husky_directory.models.common import UWDepartmentRole
from husky_directory.models.enum import PopulationType
from husky_directory.models.pws import (
    ListPersonsInput,
    ListPersonsOutput,
)
from husky_directory.models.search import Person, SearchDirectoryInput
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.search import (
    DirectorySearchService,
)
from husky_directory.services.translator import (
    ListPersonsOutputTranslator,
    PersonOutputFilter,
)


class TestDirectorySearchService:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector, mock_people, mock_injected):
        self.mock_people = mock_people
        self.pws: PersonWebServiceClient = injector.get(PersonWebServiceClient)
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
            # Allows us to
            stack.enter_context(mock_injected(PersonWebServiceClient, self.pws))
            stack.enter_context(mock_injected(LocalProxy, self.session))
            self.mock_list_persons = stack.enter_context(
                mock.patch.object(self.pws, "list_persons")
            )
            self.mock_get_explicit_href = stack.enter_context(
                mock.patch.object(self.pws, "get_explicit_href")
            )

            self.set_list_persons_output(
                mock_people.as_search_output(mock_people.published_employee)
            )
            self.client: DirectorySearchService = injector.get(DirectorySearchService)
            yield

    def set_list_persons_output(self, output: ListPersonsOutput):
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
        self.list_persons_output.persons = [person]
        request_input = SearchDirectoryInput(
            name="whatever", population=input_population
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
        self.list_persons_output.persons = [person]
        request_input = SearchDirectoryInput(
            name="whatever", population=PopulationType.employees
        )
        output = self.client.search_directory(request_input)
        output_person: Person = output.scenarios[0].populations["employees"].people[0]
        assert not output_person.departments

    def test_output_includes_box_number(self):
        person = self.mock_people.published_employee
        self.list_persons_output.persons = [person]
        output = self.client.search_directory(
            SearchDirectoryInput(name="*blah", population=PopulationType.employees)
        )
        output_person: Person = output.scenarios[0].populations["employees"].people[0]
        assert output_person.box_number == "351234"


class TestPersonOutputTranslator:
    @pytest.fixture(autouse=True)
    def initialize(self, injector, mock_people, mock_injected):
        self.injector = injector
        self.mock_people = mock_people
        self.session = {}

        with mock_injected(LocalProxy, self.session):
            yield

    @property
    def translator(self) -> ListPersonsOutputTranslator:
        return self.injector.get(ListPersonsOutputTranslator)

    @pytest.mark.parametrize("should_be_authed", (True, False))
    def test_current_request_is_authenticated(self, should_be_authed):
        if should_be_authed:
            self.session["uwnetid"] = "foo"
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
            self.session["uwnetid"] = "authuser"

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
