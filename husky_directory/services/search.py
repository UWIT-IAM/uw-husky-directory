from __future__ import annotations

from logging import Logger
from typing import Dict, List

from flask_injector import request
from injector import inject

from husky_directory.models.search import (
    DirectoryQueryScenarioOutput,
    SearchDirectoryInput,
    SearchDirectoryOutput,
)
from husky_directory.services.auth import AuthService
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.query_generator import SearchQueryGenerator
from husky_directory.services.translator import (
    ListPersonsOutputTranslator,
)
from husky_directory.util import Timer


@request
class DirectorySearchService:
    @inject
    def __init__(
        self,
        pws: PersonWebServiceClient,
        logger: Logger,
        query_generator: SearchQueryGenerator,
        pws_translator: ListPersonsOutputTranslator,
        auth_service: AuthService,
    ):
        self._pws = pws
        self.logger = logger
        self.query_generator = query_generator
        self.pws_translator = pws_translator
        self.auth_service = auth_service

    def search_directory(
        self, request_input: SearchDirectoryInput
    ) -> SearchDirectoryOutput:
        """The main interface for this service. Submits a query to PWS, filters and translates the output,
        and returns a DirectoryQueryScenarioOutput."""
        timer_context = {
            "query": request_input.dict(
                exclude_none=True,
                by_alias=True,
                exclude_properties=True,
                exclude_unset=True,
            )
        }
        timer = Timer("search_directory", context=timer_context).start()

        scenarios: List[DirectoryQueryScenarioOutput] = []
        scenario_description_indexes: Dict[str, int] = {}
        duplicate_netids = set()

        for generated in self.query_generator.generate(request_input):
            self.logger.debug(
                f"Querying: {generated.description} with "
                f"{generated.request_input.dict(exclude_unset=True, exclude_defaults=True)}"
            )
            pws_output = self._pws.list_persons(generated.request_input)
            aggregate_output = pws_output

            while pws_output.next and pws_output.next.href:
                pws_output = self._pws.get_explicit_href(pws_output.next.href)
                aggregate_output.persons.extend(pws_output.persons)

            scenario_output = DirectoryQueryScenarioOutput(
                description=generated.description,
                populations=self.pws_translator.translate_scenario(
                    aggregate_output, duplicate_netids
                ),
            )

            # Merges populations when a scenario is spread
            # over multiple queries. This is not my favorite thing,
            # and smells of a future API refactor.
            # TODO Brainstorm a better way to handle this, then create a Jira once
            # you know what the problem (and hopefully solution) is.
            if generated.description in scenario_description_indexes:
                index = scenario_description_indexes[generated.description]
                existing_scenario = scenarios[index]
                for population, results in scenario_output.populations.items():
                    if population not in existing_scenario.populations:
                        existing_scenario.populations[population].people = []
                    existing_scenario.populations[population].people.extend(
                        results.people
                    )
            else:
                scenarios.append(scenario_output)
                scenario_description_indexes[generated.description] = len(scenarios) - 1

        timer.stop(emit_log=True)
        return SearchDirectoryOutput(scenarios=scenarios)
