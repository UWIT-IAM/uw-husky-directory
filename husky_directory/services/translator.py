from typing import Dict, List, Optional, Set

from injector import inject
from werkzeug.local import LocalProxy

from husky_directory.models.base import DirectoryBaseModel
from husky_directory.models.enum import PopulationType
from husky_directory.models.pws import (
    EmployeePersonAffiliation,
    ListPersonsOutput,
    PersonOutput,
    StudentPersonAffiliation,
)
from husky_directory.models.search import (
    DirectoryQueryPopulationOutput,
    Person,
    PhoneContactMethods,
)


class PersonOutputFilter(DirectoryBaseModel):
    allowed_populations: List[PopulationType] = [PopulationType.employees]
    include_test_identities: bool = False
    duplicate_netids: Set[str] = set()

    def population_is_allowed(self, population: PopulationType) -> bool:
        return (
            "all" in self.allowed_populations
            or population.value in self.allowed_populations
        )


class ListPersonsOutputTranslator:
    """
    Translates PWS API output in to Directory API output.
    """

    @inject
    def __init__(self, session: LocalProxy):
        self._session = session

    @property
    def session(self) -> LocalProxy:
        return self._session

    @property
    def current_request_is_authenticated(self) -> bool:
        return bool(self.session.get("uwnetid"))

    def filter_person(
        self, person: PersonOutput, person_filter_paramters: PersonOutputFilter
    ) -> bool:
        """
        Given a PersonOutput, determines whether the result is valid to return to the front-end. This is needed
        because PWS does not provide query support for all fields, in particular the 'publish_in_directory' and the
        'whitepages_publish' fields. If _translate_pws_list_persons_output() is broken out into its own service,
        this should probably go along with it.

        :returns: True if the user should be included in the output, or False if they should be pruned.
        """
        if not all(
            [
                person.netid,  # Only publish identities with netids
                person.whitepages_publish,  # that want to be published
                # and that we're not already returning
                person.netid not in person_filter_paramters.duplicate_netids,
            ]
        ):
            return False

        # Only include test identities if explicitly asked
        if (
            person.is_test_entity
            and not person_filter_paramters.include_test_identities
        ):
            return False

        if person.affiliations.student:
            if not all(
                [
                    # ensure the request is authenticated
                    self.current_request_is_authenticated,
                    # ensure the user requested student data
                    person_filter_paramters.population_is_allowed(
                        PopulationType.students
                    ),
                    # Ensure the identity has elected to be published
                    person.affiliations.student.directory_listing.publish_in_directory,
                ]
            ):
                person.affiliations.student = None

        if (
            person.affiliations.employee
        ):  # Similar to above, minus the current_user check
            if not all(
                [
                    person_filter_paramters.population_is_allowed(
                        PopulationType.employees
                    ),
                    person.affiliations.employee.directory_listing.publish_in_directory,
                ]
            ):
                person.affiliations.employee = None

        # If we've pruned all the valid affiliations for this person,
        # then we won't include them in the results.
        if not any([person.affiliations.student, person.affiliations.employee]):
            return False

        return True

    def _resolve_phones(
        self,
        employee_affiliation: Optional[EmployeePersonAffiliation],
        student_affiliation: Optional[StudentPersonAffiliation],
    ) -> PhoneContactMethods:
        model = PhoneContactMethods()
        if employee_affiliation:
            model = model.copy(
                update=employee_affiliation.directory_listing.dict(
                    include={
                        "phones",
                        "pagers",
                        "voice_mails",
                        "touch_dials",
                        "faxes",
                        "mobiles",
                    },
                )
            )
        if student_affiliation:
            model.phones.append(student_affiliation.directory_listing.phone)
        return model

    def translate_scenario(
        self,
        request_output: ListPersonsOutput,
        person_filter_parameters: PersonOutputFilter,
    ) -> Dict[PopulationType, DirectoryQueryPopulationOutput]:
        results = {
            PopulationType.employees: DirectoryQueryPopulationOutput(
                population=PopulationType.employees
            ),
            PopulationType.students: DirectoryQueryPopulationOutput(
                population=PopulationType.students
            ),
        }

        def filter_(person_) -> bool:
            """A small shim around the class method to include the user-requested filters"""
            return self.filter_person(person_, person_filter_parameters)

        # Streams the list and iterates, excluding entries we don't want to return
        for person in filter(filter_, request_output.persons):
            student = person.affiliations.student
            employee = person.affiliations.employee

            person_args = {"name": person.display_name, "href": person.href}
            person_args.update(
                {
                    "phone_contacts": self._resolve_phones(
                        employee_affiliation=employee, student_affiliation=student
                    )
                }
            )

            result = Person.parse_obj(person_args)

            if employee:
                if employee.directory_listing.emails:
                    result.email = employee.directory_listing.emails[0]
                results[PopulationType.employees].people.append(result)

            if student:
                # Email will usually be the same, but just in case, we'll prefer the
                # employee email address and not overwrite it with the student's if
                # it's already set.
                if not result.email:
                    result.email = student.directory_listing.email
                results[PopulationType.students].people.append(result)
            person_filter_parameters.duplicate_netids.add(person.netid)
        return results
