from __future__ import annotations

from logging import Logger
from typing import Dict, List

from devtools import PrettyFormat
from flask_injector import request
from injector import inject

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


@request
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

        scenario_description_indexes: Dict[str, int] = {}

        for query_description, query in self.query_generator.generate(
            request_input, filter_parameters
        ):
            self.logger.info(
                f"Querying: {query_description} with "
                f"{query.dict(exclude_unset=True, exclude_defaults=True)}"
            )
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

            # Merges populations when a scenario is spread
            # over multiple queries. This is not my favorite thing,
            # and smells of a future API refactor.
            # TODO Brainstorm a better way to handle this, then create a Jira once
            # you know what the problem (and hopefully solution) is.
            if query_description in scenario_description_indexes:
                index = scenario_description_indexes[query_description]
                existing_scenario = scenarios[index]
                for population, results in scenario_output.populations.items():
                    if population not in existing_scenario.populations:
                        existing_scenario.populations[population].people = []
                    existing_scenario.populations[population].people.extend(
                        results.people
                    )
            else:
                scenarios.append(scenario_output)
                scenario_description_indexes[query_description] = len(scenarios) - 1

        return SearchDirectoryOutput(scenarios=scenarios)
