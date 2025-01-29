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
from husky_directory.models.transforms import ResultBucket


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
            if student_affiliation.directory_listing.phone:
                model.phones.append(student_affiliation.directory_listing.phone)

        return model

    @staticmethod
    def _translate_student_attributes(
        student: StudentPersonAffiliation,
        result_in_progress: Person,
    ) -> NoReturn:
        # Supports multiple emails: students have one, employees may have many.
        # Assigning student email as a single-item list for consistency.
        if student.directory_listing.email:
            result_in_progress.emails = [student.directory_listing.email]
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
        # Display all available employee emails
        # More info on: https://github.com/UWIT-IAM/uw-husky-directory/issues/174
        if employee.directory_listing.emails:
            result_in_progress.emails = employee.directory_listing.emails

        result_in_progress.box_number = employee.mail_stop
        result_in_progress.departments.extend(
            UWDepartmentRole.from_orm(position)
            for position in employee.directory_listing.positions
            # Sometimes the data we get has holes in it;
            # we ignore holey data.
            if position.department and position.title
        )

    def translate_person(self, person: PersonOutput) -> Person:
        employee = person.affiliations.employee
        student = person.affiliations.student
        result = Person(
            name=person.display_name,
            phone_contacts=self._resolve_phones(
                person.affiliations.employee, person.affiliations.student
            ),
            **person.dict()
        )
        if student:
            self._translate_student_attributes(student, result)
        if employee:
            self._translate_employee_attributes(employee, result)
        return result

    def translate_bucket(
        self, bucket: ResultBucket
    ) -> Dict[PopulationType, DirectoryQueryPopulationOutput]:
        return {
            PopulationType.employees: DirectoryQueryPopulationOutput(
                population=PopulationType.employees,
                people=[self.translate_person(p) for p in bucket.sorted_employees],
            ),
            PopulationType.students: DirectoryQueryPopulationOutput(
                population=PopulationType.students,
                people=[self.translate_person(p) for p in bucket.sorted_students],
            ),
        }

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
            "__META__": {},
        }
        num_duplicates_found = 0
        for person in request_output.persons:
            if person.netid in netid_tracker:
                num_duplicates_found += 1
                continue

            student = person.affiliations.student
            employee = person.affiliations.employee
            result = self.translate_person(person)

            if student:
                results[PopulationType.students].people.append(result)

            if employee:
                results[PopulationType.employees].people.append(result)

            netid_tracker.add(person.netid)
        results["__META__"]["duplicates"] = num_duplicates_found
        return results
