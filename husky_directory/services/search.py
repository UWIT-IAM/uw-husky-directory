from __future__ import annotations

from typing import Dict, List

from flask_injector import request
from injector import inject

from husky_directory.app_config import ApplicationConfig
from husky_directory.models.enum import AffiliationState
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
from husky_directory.models.transforms import ResultBucket
from husky_directory.services.auth import AuthService
from husky_directory.services.object_store import ObjectStorageInterface
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.query_generator import SearchQueryGenerator
from husky_directory.services.query_synchronizer import QuerySynchronizer
from husky_directory.services.reducer import NameSearchResultReducer
from husky_directory.services.translator import (
    ListPersonsOutputTranslator,
)
from husky_directory.util import AppLoggerMixIn, Timer


@request
class DirectorySearchService(AppLoggerMixIn):
    @inject
    def __init__(
        self,
        pws: PersonWebServiceClient,
        query_generator: SearchQueryGenerator,
        pws_translator: ListPersonsOutputTranslator,
        auth_service: AuthService,
        reducer: NameSearchResultReducer,
        object_store: ObjectStorageInterface,
        config: ApplicationConfig,
    ):
        self._pws = pws
        self.query_generator = query_generator
        self.pws_translator = pws_translator
        self.auth_service = auth_service
        self.reducer = reducer
        self.object_store = object_store
        self.cache_expiration_seconds = (
            config.redis_settings.default_cache_expire_seconds
        )
        self.query_sync = QuerySynchronizer(
            object_store, config.cache_expiration_settings
        )

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

        results = self._process_query(
            query,
            request_input,
            statistics,
        )

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

    def _process_query(
        self,
        query: str,
        request_input: SearchDirectoryInput,
        statistics: ListPersonsRequestStatistics,
    ) -> Dict[str, ResultBucket]:
        """
        Factored out the meat of 'search_directory_experimental' for
        a little better modularization.
        Returns a dictionary of k:v, where k is the
        queried population, and v is a ResultBucket instance containing
        the scenario results.
        """
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
                ),
                populations=request_input.requested_populations,
            )

            statistics.aggregate(pws_output.request_statistics)
            results = self.reducer.reduce_output(
                pws_output, request_input.name, results
            )

            while pws_output.next:
                pws_output = self._pws.get_explicit_href(
                    pws_output.next.href, output_type=ListPersonsOutput
                )
                results = self.reducer.reduce_output(
                    pws_output, request_input.name, results
                )

                statistics.aggregate(pws_output.request_statistics)
        return results

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
        for generated in self.query_generator.generate(request_input):
            self.logger.debug(
                f"Querying: {generated.description} with "
                f"{generated.request_input.dict(exclude_unset=True, exclude_defaults=True)}"
            )
            statistics.num_queries_generated += 1
            pws_output: ListPersonsOutput = self._pws.list_persons(
                generated.request_input, populations=request_input.requested_populations
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
        """
        The main interface for this service.
        First, checks to see if this query was already submitted in another
        request and currently running. If so, it will wait until that query completes, and
        return the results.

        Otherwise, creates a lock for this query and
        submits the query to PWS. The results are sorted and filtered
        to ensure user privacy, data accuracy, and "scenario" categorization of results.

        The results are then cached for the configured amount of time
        and returns a DirectoryQueryScenarioOutput instance.
        """
        query_id = self.query_sync.get_model_digest(request_input)
        query_key = f"query:{query_id}"

        if self.query_sync.attach(query_key):
            return SearchDirectoryOutput.parse_raw(self.object_store.get(query_key))

        with self.query_sync.lock(query_key):
            if (
                # Only name search is implemented in experimental mode right now.
                request_input.name
                # Wildcard searches are already accounted for in "classic" mode.
                and "*" not in request_input.name
            ):
                result = self.search_directory_experimental(request_input)
            else:
                result = self.search_directory_classic(request_input)
            # Keep this `put` inside the `with` context, so that the
            # status is not updated until the information
            # has been written to memory, otherwise we run the risk of
            # trying to pull the object off the cache before it's done
            # being written.
            self.object_store.put(
                query_key, result, expire_after_seconds=self.cache_expiration_seconds
            )

        return result
