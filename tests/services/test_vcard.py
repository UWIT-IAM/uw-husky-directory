from typing import List, Optional, cast
from unittest import mock

import pytest
from injector import Injector
from werkzeug.exceptions import NotFound
from werkzeug.local import LocalProxy

from husky_directory.models.pws import (
    EmployeeDirectoryListing,
    EmployeePersonAffiliation,
    EmployeePosition,
    NamedIdentity,
    PersonAffiliations,
    PersonOutput,
    StudentDirectoryListing,
    StudentPersonAffiliation,
)
from husky_directory.models.vcard import VCard, VCardPhone
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.vcard import VCardService


@pytest.fixture
def employee(generate_person) -> PersonOutput:
    positions = [
        EmployeePosition(department="Snack Eating", title="Chief of Kibble Testing"),
        EmployeePosition(department="Napping", title="Assistant Snuggler"),
    ]

    return generate_person(
        netid="employee",
        affiliations=PersonAffiliations.construct(
            employee=EmployeePersonAffiliation(
                mail_stop="381234",
                directory_listing=EmployeeDirectoryListing(
                    publish_in_directory=True,
                    phones=["1111111"],
                    pagers=["1111111"],
                    mobiles=["1111111"],
                    faxes=["2222222"],
                    touch_dials=["3333333"],
                    emails=["employee@uw.edu"],
                    positions=positions,
                    addresses=["123 Main St. Anytown, WA 98123"],
                    voice_mails=["5555555"],
                ),
            )
        ),
    )


@pytest.fixture
def student(generate_person) -> PersonOutput:
    return generate_person(
        netid="student",
        affiliations=PersonAffiliations.construct(
            student=StudentPersonAffiliation(
                directory_listing=StudentDirectoryListing(
                    publish_in_directory=True,
                    phone="4444444",
                    email="student@uw.edu",
                    departments=["Barkochemical Engineering"],
                    class_level="Goodboi",
                )
            )
        ),
    )


class TestVCardServiceAttributeResolution:
    @pytest.fixture(autouse=True)
    def initialize(self, injector: Injector):
        self.injector = injector
        self.service = injector.get(VCardService)

    def test_set_employee_vcard_attrs(self, employee):
        vcard = VCard.construct()
        self.service.set_employee_vcard_attrs(vcard, employee)

        assert vcard.phones == [
            VCardPhone(
                types=["cell", "pager", "work"],
                value="1111111",
            ),
            VCardPhone(types=["TTY-TDD"], value="3333333"),
            VCardPhone(types=["fax"], value="2222222"),
            VCardPhone(types=["MSG"], value="5555555"),
        ]

        assert vcard.email == "employee@uw.edu"
        assert vcard.departments == ["Snack Eating", "Napping"]
        assert vcard.titles == ["Chief of Kibble Testing", "Assistant Snuggler"]

    def test_set_student_vcard_attrs(self, student):
        vcard = VCard.construct()
        self.service.set_student_vcard_attrs(vcard, student)
        assert vcard.phones == [VCardPhone(types=["home"], value="4444444")]
        assert vcard.email == "student@uw.edu"
        assert vcard.titles == ["Goodboi"]
        assert vcard.departments == ["Barkochemical Engineering"]


class TestVCardServiceVCardGeneration:
    @pytest.fixture(autouse=True)
    def initialize(self, injector: Injector, mock_injected):
        self.session = cast(LocalProxy, {})

        with mock_injected(LocalProxy, self.session):
            self.service = injector.get(VCardService)
            self.pws = injector.get(PersonWebServiceClient)
            with mock_injected(PersonWebServiceClient, self.pws):
                with mock_injected(VCardService, self.service):
                    yield

        self.mock_pws_person: Optional[PersonOutput] = None

    def prepare_pws(self):
        mock_pws_get = mock.patch.object(self.pws, "_get_search_request_output").start()
        mock_pws_get.return_value = self.mock_pws_person

    def get_vcard_result(self, person: PersonOutput) -> List[str]:
        self.mock_pws_person = person
        self.prepare_pws()

        result = self.service.get_vcard("foo")
        return [line.decode("UTF-8").strip() for line in result.readlines()]

    @property
    def expected_employee_vcard(self) -> List[str]:
        return [
            "BEGIN:VCARD",
            "N:Lovelace;Ada",
            "FN:Ada Lovelace",
            "TITLE:Chief of Kibble Testing",
            "TITLE:Assistant Snuggler",
            "ORG:University of Washington;Snack Eating",
            "ORG:University of Washington;Napping",
            "EMAIL;type=INTERNET,type=WORK:employee@uw.edu",
            'TEL;type="cell,pager,work":1111111',
            'TEL;type="TTY-TDD":3333333',
            'TEL;type="fax":2222222',
            'TEL;type="MSG":5555555',
            "item1.X-ABADR:us",
            "item1.ADR;type=WORK:Box 381234;;123 Main St.;Anytown;WA;98123;US;",
            "END:VCARD",
        ]

    def test_employee_vcard(self, employee):
        self.mock_pws_person = employee
        self.prepare_pws()

        result = self.get_vcard_result(employee)
        # Go line by line to make it easier to find issues
        for i, line in enumerate(result):
            assert line == self.expected_employee_vcard[i]

    @pytest.mark.parametrize(
        "name_attrs, expected_last, expected_extras",
        [
            # Standard guessing
            (
                NamedIdentity(display_name="Alpha Beta Gamma"),
                "Gamma",
                ["Alpha", "Beta"],
            ),
            # Not sure how this would happen, but just in case, ensure we honor
            # preferences and registered names before resorting to making
            # guesses about the display name that is somehow different.
            (
                NamedIdentity(
                    preferred_first_name="Alpha",
                    display_name="Foo Bar Baz",
                    registered_first_middle_name="Alpha Beta",
                    registered_surname="Gamma",
                ),
                "Gamma",
                ["Alpha"],
            ),
            # Using first name prefs to filter the rest; aka the 'Ana Mari' case.
            (
                NamedIdentity(
                    display_name="Alpha Beta Gamma", preferred_first_name="Alpha Beta"
                ),
                "Gamma",
                ["Alpha Beta"],
            ),
            # Using preferences to override all fields;
            (
                NamedIdentity(
                    display_name="Alpha Beta Gamma Delta",
                    preferred_first_name="Alpha",
                    preferred_middle_name="Gamma",
                    preferred_last_name="Delta",
                ),
                "Delta",
                ["Alpha", "Gamma"],
            ),
            # Similar to a combined first name, but for last names.
            (
                NamedIdentity(
                    display_name="Alpha Beta St. Gamma", preferred_last_name="St. Gamma"
                ),
                "St. Gamma",
                ["Alpha", "Beta"],
            ),
            # Partial overrides for first and middle, leaving last alone.
            (
                NamedIdentity(
                    display_name="Alpha Beta Gamma",
                    preferred_first_name="Iota",
                    preferred_middle_name="Kappa",
                ),
                "Gamma",
                ["Iota", "Kappa"],
            ),
            # This person gets tired of correcting their middle name, but leaves the
            # rest alone; we can deal with that.
            (
                NamedIdentity(
                    display_name="Alpha Beta Gamma Delta",
                    preferred_middle_name="Beta Gamma",
                ),
                "Delta",
                ["Alpha", "Beta Gamma"],
            ),
        ],
    )
    def test_parse_person_name(
        self, name_attrs, expected_last, expected_extras, generate_person
    ):
        person = generate_person(**name_attrs.dict())
        last, extras = self.service.parse_person_name(person)
        assert last == expected_last
        assert extras == expected_extras

    @pytest.mark.parametrize("log_in", (True, False))
    def test_student_vcard(self, student, client, log_in):
        expected = [
            "BEGIN:VCARD",
            "N:Lovelace;Ada",
            "FN:Ada Lovelace",
            "TITLE:Goodboi",
            "ORG:University of Washington;Barkochemical Engineering",
            "EMAIL;type=INTERNET,type=WORK:student@uw.edu",
            'TEL;type="home":4444444',
            "END:VCARD",
        ]

        if log_in:
            client.get("/saml/login", follow_redirects=True)

        try:
            result = self.get_vcard_result(student)
            assert result == expected
        except NotFound:
            assert not log_in

    @pytest.mark.parametrize("log_in", (True, False))
    def test_student_employee_vcard(self, student, employee, client, log_in):
        if log_in:
            client.get("/saml/login", follow_redirects=True)

        person = student
        person.affiliations.employee = employee.affiliations.employee

        vcard = self.get_vcard_result(person)

        expected = [
            "BEGIN:VCARD",
            "N:Lovelace;Ada",
            "FN:Ada Lovelace",
            "TITLE:Goodboi",
            "TITLE:Chief of Kibble Testing",
            "TITLE:Assistant Snuggler",
            "ORG:University of Washington;Barkochemical Engineering",
            "ORG:University of Washington;Snack Eating",
            "ORG:University of Washington;Napping",
            "EMAIL;type=INTERNET,type=WORK:employee@uw.edu",
            'TEL;type="home":4444444',
            'TEL;type="cell,pager,work":1111111',
            'TEL;type="TTY-TDD":3333333',
            'TEL;type="fax":2222222',
            'TEL;type="MSG":5555555',
            "item1.X-ABADR:us",
            "item1.ADR;type=WORK:Box 381234;;123 Main St.;Anytown;WA;98123;US;",
            "END:VCARD",
        ]

        if not log_in:
            assert vcard == self.expected_employee_vcard
        else:
            assert vcard == expected
