import os
from collections import namedtuple
from logging import Logger
from typing import Dict, Optional

import requests
from devtools import PrettyFormat
from injector import inject, singleton

from husky_directory.app_config import ApplicationConfig
from husky_directory.models.pws import ListPersonsInput, ListPersonsOutput

RequestsCertificate = namedtuple("RequestsCertificate", ["cert_path", "key_path"])


@singleton
class PersonWebServiceClient:
    @inject
    def __init__(
        self,
        application_config: ApplicationConfig,
        logger: Logger,
        formatter: PrettyFormat,
    ):
        uwca_cert_path = application_config.auth_settings.uwca_cert_path
        uwca_cert_name = application_config.auth_settings.uwca_cert_name
        self.cert = RequestsCertificate(
            os.path.join(uwca_cert_path, f"{uwca_cert_name}.crt"),
            os.path.join(uwca_cert_path, f"{uwca_cert_name}.key"),
        )
        self.host = application_config.pws_settings.pws_host
        self.default_path = application_config.pws_settings.pws_default_path
        self.logger = logger
        self.formatter = formatter

    @property
    def pws_url(self):
        return f"{self.host}{self.default_path}"

    def _get_search_request_output(
        self, url: str, params: Optional[Dict] = None
    ) -> ListPersonsOutput:
        response = requests.get(
            url, cert=self.cert, params=params, headers={"Accept": "application/json"}
        )
        self.logger.info(f"[GET] {response.url} : {response.status_code}")
        response.raise_for_status()
        data = response.json()
        output = ListPersonsOutput.parse_obj(data)
        return output

    def get_next(self, page_url: str) -> ListPersonsOutput:
        """
        Given the page url (vended by PWS), returns the contents as a ListPersonsOutput. This makes it easier to
        consume multi-page results from PWS.
            Example: get_next('/identity/v2/person?name=*foo*')

            Better Example:
                list_persons_output = pws.list_persons(request_input)
                while list_persons_output.next:
                    list_persons_output = get_next(list_persons_output.next.href)
        """
        return self._get_search_request_output(f"{self.host}{page_url}")

    def list_persons(self, request_input: ListPersonsInput) -> ListPersonsOutput:
        """
        Given an input request, queries PWS and returns the output.
        For more information on this request,
        see https://it-wseval1.s.uw.edu/identity/swagger/index.html#/PersonV2/PersonSearch
        """
        request_input = request_input.payload
        url = f"{self.pws_url}/person"
        output = self._get_search_request_output(url, request_input)
        return output
