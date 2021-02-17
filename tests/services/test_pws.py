from unittest import mock

import pytest
import requests

from husky_directory.models.pws import ListPersonsInput
from husky_directory.services.pws import PersonWebServiceClient


class TestPersonWebServiceClient:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector, mock_people):
        self.injector = injector
        self.client: PersonWebServiceClient = injector.get(PersonWebServiceClient)
        self.mock_people = mock_people
        self.get_search_request_output_patcher = mock.patch.object(
            self.client, "_get_search_request_output"
        )
        self.mock_send_request = self.get_search_request_output_patcher.start()

    def test_pws_url(self):
        assert self.client.pws_url.endswith("identity/v2")

    def test_get_next(self):
        expected_url = f"{self.client.pws_url}/foobar"

        self.client.get_next("/identity/v2/foobar")
        self.mock_send_request.assert_called_once_with(expected_url)

    def test_list_persons(self):
        request_input = ListPersonsInput(display_name="test")
        self.client.list_persons(request_input)
        expected_url = f"{self.client.pws_url}/person"
        self.mock_send_request.assert_called_once_with(
            expected_url, request_input.payload
        )

    def test_get_search_request_output(self):
        mock_params = dict(abra="cadabra")
        self.get_search_request_output_patcher.stop()
        with mock.patch("husky_directory.services.pws.requests.get") as mock_get_url:
            mock_response = mock.MagicMock(requests.Response)
            mock_response.status_code = 200
            mock_response.url = "https://foo.com"
            mock_response.json.return_value = {
                "TotalCount": 0,
                "PageSize": 0,
                "PageStart": 0,
                "Persons": [],
                "Current": {},
            }
            mock_get_url.return_value = mock_response
            self.client._get_search_request_output("https://foo.com", mock_params)

        mock_get_url.assert_called_once_with(
            "https://foo.com",
            cert=self.client.cert,
            params=mock_params,
            headers={"Accept": "application/json"},
        )
