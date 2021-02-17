import re
from unittest import mock

import pytest
from bs4 import BeautifulSoup

from husky_directory.services.pws import PersonWebServiceClient


class TestSearchBlueprint:
    @pytest.fixture(autouse=True)
    def initialize(self, client, mock_people, injector):
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

    def assert_tag_with_text(self, html: BeautifulSoup, tag_name: str, text: str):
        for element in html.find_all(tag_name):
            for word in text.split():
                if word not in element.text:
                    continue
            return
        raise AssertionError(
            f"Could not find any <{tag_name}> tags with text matching {text}"
        )

    def test_json_success(self):
        response = self.flask_client.get("/search?name=foo")
        assert response.status_code == 200
        assert response.json["numResults"] == 1
        for scenario in response.json["scenarios"]:
            if scenario["people"]:
                assert (
                    scenario["people"][0]["name"]
                    == self.mock_people.contactable_person.display_name
                )
                assert (
                    scenario["people"][0]["phoneContacts"]["phones"][0]
                    == self.mock_people.contactable_person.affiliations.employee.directory_listing.phones[
                        0
                    ]
                )

    def test_render_summary_success(self):
        response = self.flask_client.post("/search", data={"name": "foo"})
        assert response.status_code == 200
        html = BeautifulSoup(response.data, "html.parser")
        results_table = html.find("table", summary="results")
        profile = self.mock_people.contactable_person
        self.assert_tag_with_text(results_table, "td", profile.display_name)
        self.assert_tag_with_text(
            results_table,
            "td",
            profile.affiliations.employee.directory_listing.phones[0],
        )
        self.assert_tag_with_text(
            results_table,
            "td",
            profile.affiliations.employee.directory_listing.emails[0],
        )

    def test_render_full_success(self):
        response = self.flask_client.post(
            "/search", data={"name": "foo", "length": "full"}
        )
        html = BeautifulSoup(response.data, "html.parser")
        listing = html.find("ul", class_="dir-listing")
        profile = self.mock_people.contactable_person
        self.assert_tag_with_text(
            listing, "li", profile.affiliations.employee.directory_listing.emails[0]
        )
        self.assert_tag_with_text(
            listing, "li", profile.affiliations.employee.directory_listing.phones[0]
        )
        self.assert_tag_with_text(html, "h3", profile.display_name)

    def test_render_no_results(self):
        self.mock_list_persons.return_value = self.mock_people.as_search_output()
        response = self.flask_client.post("/search", data={"name": "foo"})
        html = BeautifulSoup(response.data, "html.parser")
        assert not html.find("table", summary="results")
        assert html.find(string=re.compile("No matches for"))
        self.assert_tag_with_text(html, "b", 'Name is "foo"')

    def test_render_invalid_box_number(self):
        response = self.flask_client.post("/search", data={"box_number": "abcdef"})
        html = BeautifulSoup(response.data, "html.parser")
        assert not html.find("table", summary="results")
        assert html.find(string=re.compile("Encountered error"))
        assert response.status_code == 400
        self.assert_tag_with_text(html, "b", "invalid mailbox number")

    def test_render_unexpected_error(self):
        self.mock_list_persons.side_effect = RuntimeError
        response = self.flask_client.post("/search", data={"box_number": "123456"})
        html = BeautifulSoup(response.data, "html.parser")
        assert response.status_code == 500
        self.assert_tag_with_text(html, "b", "Something unexpected happened")
