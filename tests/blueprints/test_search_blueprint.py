import re
from unittest import mock

import pytest

from husky_directory.services.pws import PersonWebServiceClient


class TestSearchBlueprint:
    @pytest.fixture(autouse=True)
    def initialize(self, client, mock_people, injector, html_validator):
        self.pws_client = injector.get(PersonWebServiceClient)
        self.flask_client = client
        self.mock_people = mock_people
        self.mock_list_persons = mock.patch.object(
            self.pws_client, "list_persons"
        ).start()
        self.mock_get_next = mock.patch.object(self.pws_client, "get_next").start()
        self.mock_list_persons.return_value = mock_people.as_search_output(
            self.mock_people.contactable_person
        )
        self.mock_get_next.return_value = mock_people.as_search_output()
        self.html_validator = html_validator

    def test_json_success(self):
        response = self.flask_client.get("/search?name=foo")
        assert response.status_code == 200
        assert response.json["numResults"] == 1
        for scenario in response.json["scenarios"]:
            for population, results in scenario["populations"].items():
                if results["people"]:
                    assert (
                        results["people"][0]["name"]
                        == self.mock_people.contactable_person.display_name
                    )
                    assert (
                        results["people"][0]["phoneContacts"]["phones"][0]
                        == self.mock_people.contactable_person.affiliations.employee.directory_listing.phones[
                            0
                        ]
                    )

    def test_render_summary_success(self):
        response = self.flask_client.post("/search", data={"name": "foo"})
        assert response.status_code == 200
        profile = self.mock_people.contactable_person
        with self.html_validator.validate_response(response):
            with self.html_validator.scope("table", summary="results"):
                self.html_validator.assert_has_tag_with_text(
                    "td",
                    profile.affiliations.employee.directory_listing.phones[0],
                )
                self.html_validator.assert_has_tag_with_text(
                    "td",
                    profile.affiliations.employee.directory_listing.emails[0],
                )

    def test_render_full_success(self):
        response = self.flask_client.post(
            "/search", data={"name": "foo", "length": "full"}
        )
        profile = self.mock_people.contactable_person
        with self.html_validator.validate_response(response):
            self.html_validator.assert_has_tag_with_text("h3", profile.display_name)
            with self.html_validator.scope("ul", class_="dir-listing"):
                self.html_validator.assert_has_tag_with_text(
                    "li", profile.affiliations.employee.directory_listing.emails[0]
                )
                self.html_validator.assert_has_tag_with_text(
                    "li", profile.affiliations.employee.directory_listing.phones[0]
                )

    def test_render_no_results(self):
        self.mock_list_persons.return_value = self.mock_people.as_search_output()
        response = self.flask_client.post("/search", data={"name": "foo"})
        with self.html_validator.validate_response(response) as html:
            assert not html.find("table", summary="results")
            assert html.find(string=re.compile("No matches for"))
            self.html_validator.assert_has_tag_with_text("b", 'Name is "foo"')

    def test_render_invalid_box_number(self):
        response = self.flask_client.post("/search", data={"box_number": "abcdef"})
        assert response.status_code == 400
        with self.html_validator.validate_response(response) as html:
            assert not html.find("table", summary="results")
            assert html.find(string=re.compile("Encountered error"))
            self.html_validator.assert_has_tag_with_text("b", "invalid mailbox number")

    def test_render_unexpected_error(self):
        self.mock_list_persons.side_effect = RuntimeError
        response = self.flask_client.post("/search", data={"box_number": "123456"})
        with self.html_validator.validate_response(response):
            self.html_validator.assert_has_tag_with_text(
                "b", "Something unexpected happened"
            )

    def test_user_stays_logged_in(self):
        with self.html_validator.validate_response(self.flask_client.get("/")):
            self.html_validator.assert_not_has_student_search_options()
            self.html_validator.assert_has_sign_in_link()

        with self.html_validator.validate_response(
            self.flask_client.get("/saml/login", follow_redirects=True)
        ):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()

        with self.html_validator.validate_response(self.flask_client.get("/")):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()
