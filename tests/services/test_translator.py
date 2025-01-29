import pytest
from werkzeug.local import LocalProxy

from husky_directory.models.enum import PopulationType
from husky_directory.models.pws import ListPersonsOutput
from husky_directory.services.translator import ListPersonsOutputTranslator


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

    def test_translate_scenario(self, generate_person):
        pws_output = ListPersonsOutput.parse_obj(
            self.mock_people.as_search_output(
                self.mock_people.contactable_person,
                generate_person(),  # This empty person should be ignored
            )
        )

        netid_tracker = set()
        result = self.translator.translate_scenario(pws_output, netid_tracker)

        employees = result[PopulationType.employees]
        students = result[PopulationType.students]

        assert employees.num_results == 1
        assert students.num_results == 1

        assert employees.people[0] == students.people[0]

        person = employees.people[0]

        # Ensure student email is overwritten by employee email,
        # and verify that both employee emails are displayed instead of just one.
        # More on: https://github.com/UWIT-IAM/uw-husky-directory/blob/main/tests/conftest.py#L135
        assert person.emails == ["dawg@uw.edu", "dawg2@uw.edu"]
        assert person.box_number == "351234"
        assert person.phone_contacts.phones == ["2068675309 Ext. 4242", "19999674222"]
        assert person.departments[0].department == "Cybertronic Engineering"
        assert person.departments[0].title == "Junior"
        assert person.departments[1].department == "Haute Cuisine"
        assert person.departments[1].title == "Garde Manger"
