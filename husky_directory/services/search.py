from __future__ import annotations

from logging import Logger
from typing import Dict, List

from devtools import PrettyFormat
from injector import inject, singleton

from husky_directory.models.pws import ListPersonsOutput, PersonOutput
from husky_directory.models.search import (
    Person,
    SearchDirectoryInput,
    SearchDirectoryOutput,
)
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.query_generator import SearchQueryGenerator


@singleton
class DirectorySearchService:
    @inject
    def __init__(
        self,
        pws: PersonWebServiceClient,
        logger: Logger,
        formatter: PrettyFormat,
        query_generator: SearchQueryGenerator,
    ):
        self._pws = pws
        self.logger = logger
        self.formatter = formatter
        self.query_generator = query_generator

    @staticmethod
    def _filter_person(person: PersonOutput) -> bool:
        """
        Given a PersonOutput, determines whether the result is valid to return to the front-end. This is needed
        because PWS does not provide query support for all fields, in particular the 'publish_in_directory' and the
        'whitepages_publish' fields. If _translate_pws_list_persons_output() is broken out into its own service,
        this should probably go along with it.

        :param person:
        :return:
        """
        if (
            person.is_test_entity  # Exclude test entities
            or not person.netid  # And regid entities that have no associated netid (e.g., applicants)
            or not person.whitepages_publish  # And people who are not eligible to be published
            # And students, for now, until we have auth set up.
            or (person.affiliations.student and not person.affiliations.employee)
        ):
            return False
        # At this point, we are only [currently] working with employees. We must exclude those
        # who have chosen not to be published.
        return bool(
            person.affiliations.employee
            and person.affiliations.employee.directory_listing.publish_in_directory
        )

    def _translate_pws_list_persons_output(
        self, list_persons_output: ListPersonsOutput
    ) -> List[Person]:
        """
        This is responsible for converting the output we get from PWS and packaging it for our API. Right now it's
        very simplistic as a boilerplate iteration; this may be broken out into a service itself later.
        """
        people = []
        for person in filter(self._filter_person, list_persons_output.persons):
            person_args = {"name": person.display_name}
            if person.affiliations.employee:
                employee = person.affiliations.employee.directory_listing
                person_args["phone"] = employee.phones[0] if employee.phones else None
                person_args["email"] = employee.emails[0] if employee.emails else None
            people.append(Person.parse_obj(person_args))
            self.logger.debug(f"Successfully parsed publishable person {person_args}")
        self.logger.debug(
            f"Accepted {len(people)} valid PersonOutput "
            f"instances of {len(list_persons_output.persons)} returned by PWS."
        )
        return people

    def search_directory(
        self, request_input: SearchDirectoryInput
    ) -> Dict[str, SearchDirectoryOutput]:
        """The main interface for this service. Submits a query to PWS, filters and translates the output,
        and returns a SearchDirectoryOutput."""

        all_results = {}

        for query_description, query in self.query_generator.generate(request_input):
            pws_output = self._pws.list_persons(query)
            results = self._translate_pws_list_persons_output(pws_output)
            results.extend(self._translate_pws_list_persons_output(pws_output))
            while pws_output.next and pws_output.next.href:
                pws_output = self._pws.get_next(pws_output.next.href)
                results.extend(self._translate_pws_list_persons_output(pws_output))
            all_results[query_description] = SearchDirectoryOutput(people=results)
        return all_results
