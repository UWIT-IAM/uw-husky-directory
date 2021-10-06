from __future__ import annotations

from logging import Logger
from typing import Dict, List

from flask_injector import request
from injector import inject

from husky_directory.models.enum import AffiliationState, SearchType
from husky_directory.models.pws import (
    ListPersonsInput,
    ListPersonsOutput,
    ListPersonsRequestStatistics,
    PersonOutput,
)
from husky_directory.models.search import (
    DirectoryQueryScenarioOutput,
    Person,
    SearchDirectoryInput,
    SearchDirectoryOutput,
)
from husky_directory.services.auth import AuthService
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.query_generator import SearchQueryGenerator
from husky_directory.services.reducer import NameSearchResultReducer
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
        reducer: NameSearchResultReducer,
    ):
        self._pws = pws
        self.logger = logger
        self.query_generator = query_generator
        self.pws_translator = pws_translator
        self.auth_service = auth_service
        self.reducer = reducer

    def get_listing(self, href: str) -> Person:
        return self.pws_translator.translate_person(
            self._pws.get_explicit_href(href, output_type=PersonOutput)
        )

    def search_directory_experimental(
        self, request_input: SearchDirectoryInput
    ) -> SearchDirectoryOutput:
        """
        This new query function improves performance significantly, but is still
        being tested for accuracy and edge cases.

        This only executes one query to PWS per population requested. The
        query includes wildcards for each token the user input.

        For example: "buffy anne summers" would become a query for
        display names matching:
            "*buffy* *summers*"

        In this example, PWS would return any of the following results:
            - buffy anne summers
            - buffy "the vampire slayer" summers
            - ubuffya alsummersia
            - buffy-anne summers
            - buffy anne summers-finn

        After the results have been filtered, they are sent to the
        NameSearchResultReducer, which is responsible for sorting
        these names into appropriate buckets by relevance.
        """
        timer_context = {
            "query": request_input.dict(
                exclude_none=True,
                by_alias=True,
                exclude_properties=True,
                exclude_unset=True,
            ),
            "statistics": {},
        }
        timer = Timer("search_directory", context=timer_context).start()
        statistics = ListPersonsRequestStatistics(
            num_queries_generated=1,
            num_user_search_tokens=len(request_input.name.split()),
        )
        query = " ".join(f"*{token}*" for token in request_input.name.split())
        results = {}

        for population in request_input.requested_populations:
            pws_output: ListPersonsOutput = self._pws.list_persons(
                ListPersonsInput(
                    display_name=query,
                    employee_affiliation_state=(
                        AffiliationState.current if population == "employees" else None
                    ),
                    student_affiliation_state=(
                        AffiliationState.current if population == "students" else None
                    ),
                )
            )

            statistics.aggregate(pws_output.request_statistics)
            results = self.reducer.reduce_output(
                pws_output, request_input.name, results
            )

            while pws_output.next:
                pws_output = self._pws.get_explicit_href(
                    pws_output.next.href, output_type=ListPersonsOutput
                )
                self.reducer.reduce_output(pws_output, request_input.name, results)
                statistics.aggregate(pws_output.request_statistics)

        statistics.num_duplicates_found = self.reducer.duplicate_hit_count
        timer.context["statistics"] = statistics.dict(by_alias=True)
        timer.stop(emit_log=True)

        return SearchDirectoryOutput(
            scenarios=[
                DirectoryQueryScenarioOutput(
                    description=b.description,
                    populations=self.pws_translator.translate_bucket(b),
                )
                for b in results.values()
            ]
        )

    def search_directory_classic(
        self, request_input: SearchDirectoryInput
    ) -> SearchDirectoryOutput:
        timer_context = {
            "query": request_input.dict(
                exclude_none=True,
                by_alias=True,
                exclude_properties=True,
                exclude_unset=True,
            ),
            "statistics": {},
        }
        duplicate_netids = set()
        timer = Timer("search_directory", context=timer_context).start()

        statistics = ListPersonsRequestStatistics()
        scenarios: List[DirectoryQueryScenarioOutput] = []
        scenario_description_indexes: Dict[str, int] = {}

        if request_input.name:
            statistics.num_user_search_tokens = len(request_input.name.split())

        for generated in self.query_generator.generate(request_input):
            self.logger.debug(
                f"Querying: {generated.description} with "
                f"{generated.request_input.dict(exclude_unset=True, exclude_defaults=True)}"
            )
            statistics.num_queries_generated += 1
            pws_output: ListPersonsOutput = self._pws.list_persons(
                generated.request_input
            )
            aggregate_output = pws_output
            statistics.aggregate(pws_output.request_statistics)

            while pws_output.next and pws_output.next.href:
                pws_output = self._pws.get_explicit_href(pws_output.next.href)
                statistics.aggregate(pws_output.request_statistics)
                aggregate_output.persons.extend(pws_output.persons)

            populations = self.pws_translator.translate_scenario(
                aggregate_output, duplicate_netids
            )
            statistics.num_duplicates_found += populations.pop("__META__", {}).get(
                "duplicates", 0
            )

            scenario_output = DirectoryQueryScenarioOutput(
                description=generated.description,
                populations=populations,
            )

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

        timer.context["statistics"] = statistics.dict(by_alias=True)
        timer.stop(emit_log=True)
        return SearchDirectoryOutput(scenarios=scenarios)

    def search_directory(
        self,
        request_input: SearchDirectoryInput,
    ) -> SearchDirectoryOutput:
        """The main interface for this service. Submits a query to PWS, filters and translates the output,
        and returns a DirectoryQueryScenarioOutput."""

        if (
            SearchType(request_input.search_type) == SearchType.experimental
            # Only name search is implemented in experimental mode right now.
            and request_input.name
            # Wildcard searches are already accounted for in "classic" mode.
            and "*" not in request_input.name
        ):
            return self.search_directory_experimental(request_input)

        return self.search_directory_classic(request_input)
