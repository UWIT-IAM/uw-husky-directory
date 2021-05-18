from typing import Dict, NoReturn, Optional, Set

from injector import singleton

from husky_directory.models.common import UWDepartmentRole
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


@singleton
class ListPersonsOutputTranslator:
    """
    Translates PWS API output in to Directory API output.
    """

    @staticmethod
    def _resolve_phones(
        employee_affiliation: Optional[EmployeePersonAffiliation],
        student_affiliation: Optional[StudentPersonAffiliation],
    ) -> PhoneContactMethods:
        if employee_affiliation:
            model = PhoneContactMethods.from_orm(employee_affiliation.directory_listing)
        else:
            model = PhoneContactMethods()

        if student_affiliation:
            model.phones.append(student_affiliation.directory_listing.phone)

        return model

    @staticmethod
    def _translate_student_attributes(
        student: StudentPersonAffiliation,
        result_in_progress: Person,
    ) -> NoReturn:
        result_in_progress.email = student.directory_listing.email
        result_in_progress.departments.extend(
            UWDepartmentRole(
                title=student.directory_listing.class_level, department=dept
            )
            for dept in student.directory_listing.departments
            if dept  # Ignore data with holes in it.
        )

    @staticmethod
    def _translate_employee_attributes(
        employee: EmployeePersonAffiliation, result_in_progress: Person
    ) -> NoReturn:
        # Email will usually be the same, but just in case, we'll prefer the
        # employee email address and not overwrite it with the student's if
        # it's already set.
        if employee.directory_listing.emails:
            result_in_progress.email = employee.directory_listing.emails[0]

        result_in_progress.box_number = employee.mail_stop
        result_in_progress.departments.extend(
            UWDepartmentRole.from_orm(position)
            for position in employee.directory_listing.positions
            # Sometimes the data we get has holes in it;
            # we ignore holey data.
            if position.department and position.title
        )

    def translate_scenario(
        self, request_output: ListPersonsOutput, netid_tracker: Set[str]
    ) -> Dict[PopulationType, DirectoryQueryPopulationOutput]:
        results = {
            PopulationType.employees: DirectoryQueryPopulationOutput(
                population=PopulationType.employees
            ),
            PopulationType.students: DirectoryQueryPopulationOutput(
                population=PopulationType.students
            ),
        }

        def filter_(person_: PersonOutput) -> bool:
            """
            Ignores entities we've already catalogued [as they may have been returned
            in both the student search and the employee search], and entities
            who have had all of their guts filtered out by the output
            constraint filtering.
            """
            return person_.netid not in netid_tracker and (
                person_.affiliations.student or person_.affiliations.employee
            )

        for person in filter(filter_, request_output.persons):
            student = person.affiliations.student
            employee = person.affiliations.employee

            result = Person(
                name=person.display_name,
                sort_key=person.preferred_last_name or person.registered_surname,
                phone_contacts=self._resolve_phones(employee, student),
                **person.dict()
            )

            if student:
                self._translate_student_attributes(student, result)
                results[PopulationType.students].people.append(result)

            if employee:
                self._translate_employee_attributes(employee, result)
                results[PopulationType.employees].people.append(result)

            netid_tracker.add(person.netid)
        return results
