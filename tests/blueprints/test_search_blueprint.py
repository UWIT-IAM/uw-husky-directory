import re
from unittest import mock

import pytest
from bs4 import BeautifulSoup

from husky_directory.models.pws import ListPersonsInput, ListPersonsOutput
from husky_directory.services.pws import PersonWebServiceClient


class TestSearchBlueprint:
    @pytest.fixture(autouse=True)
    def initialize(self, client, mock_person_data, injector):
        self.pws_client = injector.get(PersonWebServiceClient)
        self.flask_client = client
        self.mock_list_persons = mock.patch.object(
            self.pws_client, "list_persons"
        ).start()
        self.mock_get_next = mock.patch.object(self.pws_client, "get_next").start()
        self.mock_list_persons.return_value = ListPersonsOutput.parse_obj(
            mock_person_data
        )
        del mock_person_data["Next"]
        self.mock_get_next.return_value = ListPersonsOutput.parse_obj(mock_person_data)

    def test_json_success(self):
        response = self.flask_client.get("/search?name=foo")
        assert response.status_code == 200
        assert response.json["numResults"] > 0

    def test_render_success(self):
        response = self.flask_client.post("/search", data={"name": "foo"})
        assert response.status_code == 200
        html = BeautifulSoup(response.data, "html.parser")
        assert html.find("table", summary="results")

    def test_render_no_results(self):
        self.mock_list_persons.return_value = ListPersonsOutput(
            persons=[],
            page_start=0,
            total_count=0,
            page_size=0,
            current=ListPersonsInput(),
        )
        response = self.flask_client.post("/search", data={"name": "foo"})
        html = BeautifulSoup(response.data, "html.parser")
        assert not html.find("table", summary="results")
        assert html.find(string=re.compile("No matches for"))
        for e in html.find_all("b"):
            # Newlines in the rendered output make it impossible for BeautifulSoup to find
            # the text exactly, which is annoying, so we can just verify that all the pieces are
            # together in the same <b> tag.
            text = e.string.strip()
            if "Name" in text and 'is "foo"' in text:
                return
        raise AssertionError("Not able to find correct results message in output")

    def test_render_invalid_box_number(self):
        response = self.flask_client.post("/search", data={"box_number": "abcdef"})
        html = BeautifulSoup(response.data, "html.parser")
        assert not html.find("table", summary="results")
        assert html.find(string=re.compile("Encountered error"))
        assert response.status_code == 400
        for e in html.find_all("b"):
            if "invalid mailbox number" in e.text.strip():
                return
        raise AssertionError("Not able to find correct error message in output")

    def test_render_unexpected_error(self):
        self.mock_list_persons.side_effect = RuntimeError
        response = self.flask_client.post("/search", data={"box_number": "123456"})
        html = BeautifulSoup(response.data, "html.parser")
        assert response.status_code == 500
        for e in html.find_all("b"):
            if "Something unexpected happened" in e.text.strip():
                return
        raise AssertionError("Not able to find correct error message in output")
