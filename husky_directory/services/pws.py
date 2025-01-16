import os
from collections import namedtuple
from functools import partial
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import requests
from flask_injector import request
from injector import inject
from werkzeug.exceptions import NotFound

from husky_directory.app_config import ApplicationConfig
from husky_directory.models.common import RecordConstraint
from husky_directory.models.enum import PopulationType
from husky_directory.models.pws import (
    ListPersonsInput,
    ListPersonsOutput,
    ListPersonsRequestStatistics,
    PersonOutput,
)
from husky_directory.services.auth import AuthService
from husky_directory.util import AppLoggerMixIn, timed

RequestsCertificate = namedtuple("RequestsCertificate", ["cert_path", "key_path"])


OutputReturnType = TypeVar(
    "OutputReturnType", bound=Union[ListPersonsOutput, PersonOutput]
)


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
    if field and attr in field:
        del field[attr]
    return True


@request
class PersonWebServiceClient(AppLoggerMixIn):
    _GLOBAL_CONSTRAINTS = [
        RecordConstraint(
            # If the identity has no netid, we are not interested
            # in the record.
            namespace="UWNetID",
            predicate=bool,
        ),
        RecordConstraint(
            # If the identity is not eligible for publication,
            # we are not interested in the record.
            namespace="WhitepagesPublish",
            predicate=bool,
        ),
        RecordConstraint(
            # TODO: Support including test entities here,
            # which will need a minor refactor of how that param
            # is passed around. For now, we simply invert
            # the bool representation: if we have a test entity,
            # then we return False (and exclude the record).
            namespace="IsTestEntity",
            predicate=lambda v: not bool(v),
        ),
        RecordConstraint(
            # If there is a student affiliation and the affiliation's
            # publication flag is true, then accept it;
            # otherwise clear the affiliation from the record and
            # continue processing.
            namespace=(
                "PersonAffiliations.StudentPersonAffiliation.StudentWhitePages.PublishInDirectory"
            ),
            predicate=bool,
            failure_callback=partial(
                clear_namespace, "PersonAffiliations.StudentPersonAffiliation"
            ),
        ),
        RecordConstraint(
            # If there is an employee affiliation and the affiliation's
            # publication flag is true, then accept it;
            # otherwise clear the affiliation from the record and
            # continue processing.
            namespace=(
                "PersonAffiliations.EmployeePersonAffiliation.EmployeeWhitePages.PublishInDirectory"
            ),
            predicate=bool,
            failure_callback=partial(
                clear_namespace, "PersonAffiliations.EmployeePersonAffiliation"
            ),
        ),
    ]

    @inject
    def __init__(
        self,
        application_config: ApplicationConfig,
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
        self.auth = auth

    @property
    def pws_url(self):
        return f"{self.host}{self.default_path}"

    @timed
    def validate_connection(self):
        response = requests.get(self.pws_url)
        response.raise_for_status()

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
        output = self._get_search_request_output(url, params)
        if output_type is ListPersonsOutput:
            statistics = ListPersonsRequestStatistics(
                num_results_returned=len(output["Persons"]),
                num_pages_returned=1,
            )
            # Pre-process the output to remove items that do not meet
            # the provided client-side constraints.
            output["Persons"] = list(
                filter(
                    partial(self._filter_output_item, constraints), output["Persons"]
                )
            )
            statistics.num_results_ignored = max(
                statistics.num_results_returned - len(output["Persons"]), 0
            )
            output["request_statistics"] = statistics
        elif output_type is PersonOutput:
            if not self._filter_output_item(constraints, output):
                raise NotFound
        output = output_type.parse_obj(output)
        return output

    def _get_search_request_output(
        self,
        url: str,
        params: Optional[Dict] = None,
    ) -> Dict:
        response = requests.get(
            url, cert=self.cert, params=params, headers={"Accept": "application/json"}
        )
        self.logger.info(f"[GET] {response.url} : {response.status_code}")
        response.raise_for_status()
        data = response.json()
        return data

    def _filter_output_item(
        self,
        constraints: List[RecordConstraint],
        target: Dict,
    ) -> bool:
        affiliations: Dict = target.get("PersonAffiliations")

        if affiliations and not self.auth.request_is_authenticated:
            # If the request is not authenticated, trash student
            # data here and now, before it gets exported into
            # a model.
            affiliations.pop("StudentPersonAffiliation", None)
        if not affiliations.get("EmployeePersonAffiliation"):
            affiliations.pop("EmployeePersonAffiliation", None)

        # Don't use elif here, because the first
        # predicate (above) may modify the dictionary, so we
        # must re-check that the dict is populated.
        if not affiliations:
            return False

        return all(constraint.matches(target) for constraint in constraints)

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
        return self._GLOBAL_CONSTRAINTS

    def list_persons(
        self, request_input: ListPersonsInput, populations=List[PopulationType]
    ) -> ListPersonsOutput:
        """
        Given an input request, queries PWS and returns the output.
        For more information on this request,
        see https://wseval.s.uw.edu/identity/swagger/index.html#/PersonV2/PersonSearch
        """
        payload = request_input.payload
        constraints = self.global_constraints + request_input.constraints

        # These constraints can only be created when a request is made, because
        # this method only knows about one population at a time, as each
        # list_persons query can only target one "OR" population.
        student_population_constraint = RecordConstraint(
            namespace="PersonAffiliations.StudentPersonAffiliation",
            predicate=lambda v: "students" in populations,
            failure_callback=partial(
                clear_namespace, "PersonAffiliations.StudentPersonAffiliation"
            ),
        )
        employee_population_constraint = RecordConstraint(
            namespace="PersonAffiliations.EmployeePersonAffiliation",
            predicate=lambda v: "employees" in populations,
            failure_callback=partial(
                clear_namespace, "PersonAffiliations.EmployeePersonAffiliation"
            ),
        )
        constraints.insert(0, student_population_constraint)
        constraints.insert(0, employee_population_constraint)

        url = f"{self.pws_url}/person"
        output = self._get_sanitized_request_output(
            url, payload, constraints=constraints
        )

        return output
