import os
from collections import namedtuple
from functools import partial
from logging import Logger
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, cast

import requests
from devtools import PrettyFormat
from flask_injector import request
from injector import inject
from werkzeug.exceptions import NotFound

from husky_directory.app_config import ApplicationConfig
from husky_directory.models.common import RecordConstraint
from husky_directory.models.pws import (
    ListPersonsInput,
    ListPersonsOutput,
    PersonOutput,
)
from husky_directory.services.auth import AuthService

RequestsCertificate = namedtuple("RequestsCertificate", ["cert_path", "key_path"])


OutputReturnType = TypeVar(
    "OutputReturnType", bound=Union[ListPersonsOutput, PersonOutput]
)


@request
class PersonWebServiceClient:
    @inject
    def __init__(
        self,
        application_config: ApplicationConfig,
        logger: Logger,
        formatter: PrettyFormat,
        auth: AuthService,
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
        self.auth = auth

    @property
    def pws_url(self):
        return f"{self.host}{self.default_path}"

    def _get_sanitized_request_output(
        self,
        url: str,
        params: Optional[Dict] = None,
        constraints: Optional[List[RecordConstraint]] = None,
        output_type: Type[OutputReturnType] = ListPersonsOutput,
    ) -> OutputReturnType:
        """
        Applies filters to the output. This puts almost all of the filtering
        right above the request layer using a unified interface, as opposed to
        filtering in different ways at different times.

        Essentially, we know that in the Cloud Native Directory product, we always want to
        apply certain filters against the data, so we will prune it right at the source so that
        the other services in our application don't have to validate data state.

        :return: The output; always returns a value, unless PWS raises an error.
        """
        constraints = constraints or self.global_constraints
        output = self._get_search_request_output(url, params, output_type)
        if output_type is ListPersonsOutput:
            output = cast(ListPersonsOutput, output)
            # Post-process the output to remove items that do not meet
            # the provided client-side constraints.
            output.persons = list(
                filter(partial(self._filter_output_item, constraints), output.persons)
            )
        elif output_type is PersonOutput:
            output = cast(PersonOutput, output)
            if not self._filter_output_item(constraints, output):
                raise NotFound
        return output

    def _get_search_request_output(
        self,
        url: str,
        params: Optional[Dict] = None,
        output_type: Type[OutputReturnType] = ListPersonsOutput,
    ) -> OutputReturnType:
        response = requests.get(
            url, cert=self.cert, params=params, headers={"Accept": "application/json"}
        )
        self.logger.info(f"[GET] {response.url} : {response.status_code}")
        response.raise_for_status()
        data = response.json()
        output = output_type.parse_obj(data)
        return output

    def _filter_output_item(
        self, constraints: List[RecordConstraint], target: PersonOutput
    ) -> bool:
        if target.affiliations.student and not self.auth.request_is_authenticated:
            target.affiliations.student = None

        for constraint in constraints:
            if not constraint.matches(target):
                return False

        return bool(target.affiliations.student) or bool(target.affiliations.employee)

    def get_explicit_href(
        self, page_url: str, output_type: Type[OutputReturnType] = ListPersonsOutput
    ) -> OutputReturnType:
        """
        Given the page url (vended by PWS), returns the contents as a ListPersonsOutput. This makes it easier to
        consume multi-page results from PWS.
            Example: get_explicit_href('/identity/v2/person?name=*foo*')

            Better Example:
                list_persons_output = pws.list_persons(request_input)
                while list_persons_output.next:
                    list_persons_output = get_explicit_href(list_persons_output.next.href)
        """
        return self._get_sanitized_request_output(
            f"{self.host}{page_url}", output_type=output_type
        )

    @property
    def global_constraints(self) -> List[RecordConstraint]:
        """
        These constraints are applied to every public request method in this application.
        """

        def clear_namespace(namespace, record: Any) -> bool:
            """
            This callback allows attributes to be cleared if they
            do not match the criteria, instead of throwing away the entire record.
            Practically: if the user has opted out of employee or student publication,
            then we null the respective attributes.
            """
            ns = namespace.split(".")
            attr = ns.pop(
                -1
            )  # Allows us to resolve to the level _above_ the field being cleared
            constraint = RecordConstraint.construct(namespace=".".join(ns))
            field = constraint.resolve_namespace(record)
            if field:
                setattr(field, attr, None)
            return True

        return [
            RecordConstraint(
                # If the identity has no netid, we are not interested
                # in the record.
                namespace="netid",
                predicate=bool,
            ),
            RecordConstraint(
                # If the identity is not eligible for publication,
                # we are not interested in the record.
                namespace="whitepages_publish",
                predicate=bool,
            ),
            RecordConstraint(
                # TODO: Support including test entities here,
                # which will need a minor refactor of how that param
                # is passed around. For now, we simply invert
                # the bool representation: if we have a test entity,
                # then we return False (and exclude the record).
                namespace="is_test_entity",
                predicate=lambda v: not bool(v),
            ),
            RecordConstraint(
                # If there is a student affiliation and the affiliation's
                # publication flag is true, then accept it;
                # otherwise clear the affiliation from the record and
                # continue processing.
                namespace="affiliations.student.directory_listing.publish_in_directory",
                predicate=bool,
                failure_callback=partial(clear_namespace, "affiliations.student"),
            ),
            RecordConstraint(
                # If there is an employee affiliation and the affiliation's
                # publication flag is true, then accept it;
                # otherwise clear the affiliation from the record and
                # continue processing.
                namespace="affiliations.employee.directory_listing.publish_in_directory",
                predicate=bool,
                failure_callback=partial(clear_namespace, "affiliations.employee"),
            ),
        ]

    def list_persons(self, request_input: ListPersonsInput) -> ListPersonsOutput:
        """
        Given an input request, queries PWS and returns the output.
        For more information on this request,
        see https://it-wseval1.s.uw.edu/identity/swagger/index.html#/PersonV2/PersonSearch
        """
        payload = request_input.payload
        constraints = self.global_constraints + request_input.constraints

        url = f"{self.pws_url}/person"
        output = self._get_sanitized_request_output(
            url, payload, constraints=constraints
        )

        return output
