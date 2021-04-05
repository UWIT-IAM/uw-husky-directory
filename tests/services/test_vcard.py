from typing import List, Optional, cast
from unittest import mock

import pytest
from injector import Injector
from werkzeug.exceptions import Forbidden
from werkzeug.local import LocalProxy

from husky_directory.models.pws import (
    EmployeeDirectoryListing,
    EmployeePersonAffiliation,
    EmployeePosition,
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
        EmployeePosition(
            department="Snack Eating", title="Chief of Kibble Testing", primary=True
        ),
        EmployeePosition(
            department="Napping", title="Assistant Snuggler", primary=False
        ),
    ]

    return generate_person(
        netid="employee",
        affiliations=PersonAffiliations.construct(
            employee=EmployeePersonAffiliation(
                directory_listing=EmployeeDirectoryListing(
                    publish_in_directory=True,
                    phones=["1111111"],
                    pagers=["1111111"],
                    mobiles=["1111111"],
                    faxes=["2222222"],
                    touch_dials=["3333333"],
                    emails=["employee@uw.edu"],
                    positions=positions,
                )
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

    def test_request_is_authenticated(self, client):
        assert not self.service.request_is_authenticated
        client.get("/saml/login", follow_redirects=True)
        assert self.service.request_is_authenticated
        client.get("/saml/logout", follow_redirects=True)
        assert not self.service.request_is_authenticated

    def test_set_employee_vcard_attrs(self, employee):
        vcard = VCard.construct()
        self.service.set_employee_vcard_attrs(vcard, employee)

        assert vcard.phones == [
            VCardPhone(
                types=["pager", "text", "voice"],
                value="1111111",
            ),
            VCardPhone(types=["textphone"], value="3333333"),
            VCardPhone(types=["fax"], value="2222222"),
        ]

        assert vcard.email == "employee@uw.edu"
        assert vcard.departments == ["Snack Eating", "Napping"]
        assert vcard.titles == ["Chief of Kibble Testing", "Assistant Snuggler"]

    def test_set_student_vcard_attrs(self, student):
        vcard = VCard.construct()
        self.service.set_student_vcard_attrs(vcard, student)
        assert vcard.phones == [VCardPhone(types=["voice"], value="4444444")]
        assert vcard.email == "student@uw.edu"
        assert vcard.titles == ["Goodboi"]
        assert vcard.departments == ["Barkochemical Engineering"]


class TestVCardServiceVCardGeneration:
    @pytest.fixture(autouse=True)
    def initialize(self, injector: Injector):
        self.service = injector.get(VCardService)
        self.pws = injector.get(PersonWebServiceClient)
        self.session = cast(LocalProxy, {})

        orig_get = injector.get

        def mock_get(cls_):
            if cls_ == PersonWebServiceClient:
                return self.pws
            if cls_ == LocalProxy:
                return self.session
            return orig_get(cls_)

        mock.patch.object(injector, "get").start().side_effect = mock_get
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
            "ORG:Snack Eating",
            "ORG:Napping",
            "EMAIL;type=WORK:employee@uw.edu",
            'TEL;type="pager,text,voice":1111111',
            'TEL;type="textphone":3333333',
            'TEL;type="fax":2222222',
            "END:VCARD",
        ]

    def test_employee_vcard(self, employee):
        self.mock_pws_person = employee
        self.prepare_pws()

        result = self.get_vcard_result(employee)
        # Go line by line to make it easier to find issues
        for i, line in enumerate(result):
            assert line == self.expected_employee_vcard[i]

    @pytest.mark.parametrize("log_in", (True, False))
    def test_student_vcard(self, student, client, log_in):
        expected = [
            "BEGIN:VCARD",
            "N:Lovelace;Ada",
            "FN:Ada Lovelace",
            "TITLE:Goodboi",
            "ORG:Barkochemical Engineering",
            "EMAIL;type=WORK:student@uw.edu",
            'TEL;type="voice":4444444',
            "END:VCARD",
        ]

        if log_in:
            client.get("/saml/login", follow_redirects=True)

        try:
            result = self.get_vcard_result(student)
            for i, line in enumerate(result):
                assert line == expected[i]
        except Forbidden:
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
            "ORG:Barkochemical Engineering",
            "ORG:Snack Eating",
            "ORG:Napping",
            "EMAIL;type=WORK:employee@uw.edu",
            'TEL;type="pager,text,voice":1111111',
            'TEL;type="textphone":3333333',
            'TEL;type="fax":2222222',
            "END:VCARD",
        ]

        if not log_in:
            assert vcard == self.expected_employee_vcard
        else:
            assert vcard == expected
