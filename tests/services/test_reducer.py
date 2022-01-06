import pytest

from husky_directory.models.pws import ListPersonsOutput, NamedIdentity
from husky_directory.services.reducer import (
    NameSearchResultReducer,
    NameQueryResultAnalyzer,
)


class TestNamedIdentityAnalyzer:
    identity = NamedIdentity(display_name="Alpha Beta Gamma")

    @pytest.mark.parametrize(
        "query, bucket",
        [
            ("alpha beta gamma", 'Name is "alpha beta gamma"'),
            ("gamma", 'Last name is "gamma"'),
            ("alpha", 'First name is "alpha"'),
            ("gam", 'Last name starts with "gam"'),
            ("alp", 'First name starts with "alp"'),
            ("alpha eta gamma", 'Name is similar to "alpha eta gamma"'),
            ("alp bet gam", 'Name contains all of "alp," "bet," and "gam"'),
            ("al ga", 'Name contains "al" and "ga"'),
            ("eta", 'Name contains "eta"'),
        ],
    )
    def test_relevant_bucket(self, query, bucket):
        assert (
            NameQueryResultAnalyzer(self.identity, query).relevant_bucket[0] == bucket
        )


class TestNameSearchResultReducer:
    @pytest.fixture(autouse=True)
    def initialize(self, injector, mock_people):
        self.reducer = injector.get(NameSearchResultReducer)
        self.mock_people = mock_people
        self.search_results = ListPersonsOutput.parse_obj(
            mock_people.as_search_output(
                mock_people.published_employee.copy(
                    update=dict(
                        display_name="Alpha Gamma",
                        registered_first_middle_name="Alpha Beta",
                        registered_surname="Gamma",
                        preferred_first_name="Alpha",
                        preferred_last_name="Gamma",
                        netid="alphag",
                    )
                ),
                mock_people.published_employee.copy(
                    update=dict(
                        display_name="Alpha Gamma",
                        registered_first_middle_name="Alpha Beta",
                        registered_surname="Gamma",
                        preferred_first_name="Alpha",
                        preferred_last_name="Gamma",
                        netid="alphag",  # duplicate entry
                    )
                ),
                mock_people.published_employee.copy(
                    update=dict(
                        display_name="Does not belong",
                        registered_first_middle_name="Does not",
                        registered_surname="belong",
                        preferred_first_name="doesn't",
                        preferred_last_name="belong",
                        netid="waldo",
                    )
                ),
            )
        )

    def test_reduce_output(self):
        result = self.reducer.reduce_output(self.search_results, "alpha gamma")
        assert len(result) == 1
        assert result.get('Name is "alpha gamma"')
