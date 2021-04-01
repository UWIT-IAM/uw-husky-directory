import re
from unittest import mock

import pytest
from inflection import titleize

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
        response = self.flask_client.post("/search", data={"query": "foo"})
        assert response.status_code == 200
        profile = self.mock_people.contactable_person
        with self.html_validator.validate_response(response) as html:
            with self.html_validator.scope("table", summary="results"):
                self.html_validator.assert_has_tag_with_text(
                    "td",
                    profile.affiliations.employee.directory_listing.phones[0],
                )
                self.html_validator.assert_has_tag_with_text(
                    "td",
                    profile.affiliations.employee.directory_listing.emails[0],
                )
            assert "autofocus" not in html.find("input", attrs={"name": "query"}).attrs

    def test_render_full_success(self):
        response = self.flask_client.post(
            "/search", data={"query": "foo", "length": "full"}
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
        response = self.flask_client.post("/search", data={"query": "foo"})
        with self.html_validator.validate_response(response) as html:
            assert not html.find("table", summary="results")
            assert html.find(string=re.compile("No matches for"))
            self.html_validator.assert_has_tag_with_text("b", 'Name is "foo"')

    def test_render_invalid_box_number(self):
        response = self.flask_client.post(
            "/search", data={"query": "abcdef", "method": "box_number"}
        )
        assert response.status_code == 400
        with self.html_validator.validate_response(response) as html:
            assert not html.find("table", summary="results")
            assert html.find(string=re.compile("Encountered error"))
            self.html_validator.assert_has_tag_with_text("b", "invalid box number")

    def test_render_unexpected_error(self):
        self.mock_list_persons.side_effect = RuntimeError
        response = self.flask_client.post(
            "/search", data={"query": "123456", "method": "box_number"}
        )
        with self.html_validator.validate_response(response):
            self.html_validator.assert_has_tag_with_text(
                "b", "Something unexpected happened"
            )

    def test_user_login_flow(self):
        with self.html_validator.validate_response(self.flask_client.get("/")):
            self.html_validator.assert_not_has_student_search_options()
            self.html_validator.assert_has_sign_in_link()

        with self.html_validator.validate_response(
            self.flask_client.get("/saml/login", follow_redirects=True)
        ):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()

    def test_user_stays_logged_in_after_search(self):
        self.test_user_login_flow()
        with self.html_validator.validate_response(
            self.flask_client.post(
                "/search",
                data={
                    "query": "foo",
                    "method": "name",
                },
            )
        ):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()

    def test_user_stays_logged_in_revisit(self):
        self.test_user_login_flow()
        with self.html_validator.validate_response(self.flask_client.get("/")):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()

    @pytest.mark.parametrize(
        "search_field, search_value",
        [
            ("name", "bugbear"),
            ("phone", "abcdefg"),
            ("department", "UW-IT IAM"),
            ("box_number", "12345"),
            ("email", "foo@bar.com"),
        ],
    )
    def test_no_matches(self, search_field, search_value):
        query_output = self.mock_people.as_search_output()
        query_output.persons = []
        query_output.total_count = 0
        query_output.next = None
        self.mock_list_persons.return_value = query_output
        with self.html_validator.validate_response(
            self.flask_client.post(
                "/search", data={"method": search_field, "query": search_value}
            )
        ):
            self.html_validator.assert_has_tag_with_text(
                "p", f'no matches for {titleize(search_field)} is "{search_value}"'
            )
