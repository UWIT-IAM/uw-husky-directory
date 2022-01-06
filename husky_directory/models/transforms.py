from typing import List, NoReturn

from husky_directory.models.base import DirectoryBaseModel
from husky_directory.models.pws import PersonOutput
from husky_directory.services.name_analyzer import NameAnalyzer


class ResultBucket(DirectoryBaseModel):
    description: str
    students: List[PersonOutput] = []
    employees: List[PersonOutput] = []

    # The relevance is an index value to help sort the
    # buckets themselves. The lower the value, the closer
    # to the beginning of a list of buckets this bucket will be.
    relevance: int = 0

    def add_person(self, pws_person: PersonOutput) -> NoReturn:
        if pws_person.affiliations.employee:
            self.employees.append(pws_person)
        if pws_person.affiliations.student:
            self.students.append(pws_person)

    @property
    def sorted_students(self) -> List[PersonOutput]:
        return sorted(self.students, key=lambda p: NameAnalyzer(p).sort_key)

    @property
    def sorted_employees(self) -> List[PersonOutput]:
        return sorted(self.employees, key=lambda p: NameAnalyzer(p).sort_key)
