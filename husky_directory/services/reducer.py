from collections import OrderedDict
from functools import cached_property
from logging import Logger
from typing import Dict, Optional, Tuple

from injector import inject

from husky_directory.models.pws import ListPersonsOutput, NamedIdentity, ResultBucket
from husky_directory.util import is_similar, readable_list


class NamedIdentityAnalyzer:
    def __init__(
        self, entity: NamedIdentity, query_string: str, fuzziness: float = 0.25
    ):
        self.entity = entity
        self.query_string = query_string
        self.fuzziness = fuzziness

        self.cmp_name = entity.display_name.lower()
        self.cmp_surname = entity.displayed_surname.lower()
        self.cmp_first_name = entity.displayed_first_name.lower()
        self.cmp_query = query_string.lower()
        self.cmp_query_tokens = self.cmp_query.split()

        self.num_query_tokens = len(self.cmp_query_tokens)

    @cached_property
    def name_matches_query(self) -> bool:
        return self.cmp_name == self.cmp_query

    @cached_property
    def last_name_matches_query(self) -> bool:
        return self.cmp_surname == self.cmp_query

    @cached_property
    def first_name_matches_query(self) -> bool:
        return self.cmp_first_name == self.cmp_query

    @cached_property
    def first_name_starts_with_query(self) -> bool:
        return self.cmp_first_name.startswith(self.cmp_query)

    @cached_property
    def last_name_starts_with_query(self) -> bool:
        return self.cmp_surname.startswith(self.cmp_query)

    @cached_property
    def all_query_tokens_in_name(self) -> bool:
        return all(token in self.cmp_name for token in self.cmp_query_tokens)

    @cached_property
    def name_is_similar_to_query(self) -> bool:
        return is_similar(
            query=self.cmp_query, display_name=self.cmp_name, fuzziness=self.fuzziness
        )

    @cached_property
    def relevant_bucket(self) -> Optional[Tuple[str, int]]:
        """
        :return: A tuple whose first entry is the bucket description, and whose second
                 entry is the bucket priority/sort key. This helps to make sure that
                 results are printed to users in order of (what we declare as) relevance.
        """
        if self.name_matches_query:
            return f'Name is "{self.query_string}"', 1
        if self.last_name_matches_query:
            return f'Last name is "{self.query_string}"', 2
        if self.first_name_matches_query:
            return f'First name is "{self.query_string}"', 3
        if self.last_name_starts_with_query:
            return f'Last name starts with "{self.query_string}"', 4
        if self.first_name_starts_with_query:
            return f'First name starts with "{self.query_string}"', 5
        if self.name_is_similar_to_query:
            return f'Name is similar to "{self.query_string}"', 6
        if self.all_query_tokens_in_name:
            readable = readable_list(self.query_string.split())
            if len(self.cmp_query_tokens) > 2:
                return f"Name contains all of {readable}", 7
            return f"Name contains {readable}", 7


class NameSearchResultReducer:
    @inject
    def __init__(self, logger: Logger):
        self.duplicate_netids = set()
        self.duplicate_hit_count = 0
        self.logger = logger

    def reduce_output(
        self,
        output: ListPersonsOutput,
        query_string: str,
        buckets: Optional[Dict[str, ResultBucket]] = None,
    ) -> Dict[str, ResultBucket]:
        buckets = buckets or {}

        for pws_person in output.persons:
            if pws_person.netid in self.duplicate_netids:
                self.duplicate_hit_count += 1
                continue
            analyzer = NamedIdentityAnalyzer(
                entity=pws_person, query_string=query_string
            )
            bucket, relevance = analyzer.relevant_bucket or (None, None)

            if not bucket:
                # This is unlikely to happen unless PWS starts serving
                # some highly irrelevant results for some reason
                self.logger.info(
                    f"Could not find relevant bucket for person {pws_person.display_name} matching "
                    f"query {query_string}"
                )
                continue

            if bucket not in buckets:
                buckets[bucket] = ResultBucket(description=bucket, relevance=relevance)

            buckets[bucket].add_person(pws_person)
            self.duplicate_netids.add(pws_person.netid)

        return OrderedDict(sorted(buckets.items(), key=lambda i: i[1].relevance))
