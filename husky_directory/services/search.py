from __future__ import annotations

from logging import Logger
from typing import List

from devtools import PrettyFormat
from injector import inject, singleton

from husky_directory.models.search import (
    DirectoryQueryScenarioOutput,
    SearchDirectoryInput,
    SearchDirectoryOutput,
)
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.query_generator import SearchQueryGenerator
from husky_directory.services.translator import (
    ListPersonsOutputTranslator,
    PersonOutputFilter,
)


@singleton
class DirectorySearchService:
    @inject
    def __init__(
        self,
        pws: PersonWebServiceClient,
        logger: Logger,
        formatter: PrettyFormat,
        query_generator: SearchQueryGenerator,
        pws_translator: ListPersonsOutputTranslator,
    ):
        self._pws = pws
        self.logger = logger
        self.formatter = formatter
        self.query_generator = query_generator
        self.pws_translator = pws_translator

    def search_directory(
        self, request_input: SearchDirectoryInput
    ) -> SearchDirectoryOutput:
        """The main interface for this service. Submits a query to PWS, filters and translates the output,
        and returns a DirectoryQueryScenarioOutput."""
        scenarios: List[DirectoryQueryScenarioOutput] = []
        filter_parameters = PersonOutputFilter(
            allowed_populations=request_input.requested_populations,
            include_test_identities=request_input.include_test_identities,
        )

        for query_description, query in self.query_generator.generate(request_input):
            pws_output = self._pws.list_persons(query)
            aggregate_output = pws_output
            while pws_output.next and pws_output.next.href:
                pws_output = self._pws.get_explicit_href(pws_output.next.href)
                aggregate_output.persons.extend(pws_output.persons)

            scenario_output = DirectoryQueryScenarioOutput(
                description=query_description,
                populations=self.pws_translator.translate_scenario(
                    aggregate_output, filter_parameters
                ),
            )
            scenarios.append(scenario_output)

        return SearchDirectoryOutput(scenarios=scenarios)
