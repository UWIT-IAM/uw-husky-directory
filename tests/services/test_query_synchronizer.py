import time

import pytest

from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.object_store import InMemoryObjectStorage
from husky_directory.services.query_synchronizer import QueryStatus, QuerySynchronizer


class TestQuerySynchronizer:
    @pytest.fixture(autouse=True)
    def initialize(self, injector, app_config):
        self.config = app_config
        self.cache = InMemoryObjectStorage()
        self.request = SearchDirectoryInput(name="foo")
        self.sync = QuerySynchronizer(self.cache, app_config.cache_expiration_settings)
        self.query_id = self.sync.get_model_digest(self.request)

    def test_query_sync(self):
        with self.sync.lock(self.query_id):
            assert self.sync.get_status(self.query_id) == QueryStatus.in_progress

        assert self.sync.get_status(self.query_id) == QueryStatus.completed

    def test_query_sync_error(self):
        with pytest.raises(RuntimeError):
            with self.sync.lock(self.query_id):
                raise RuntimeError("oh dear!")

        assert self.sync.get_status(self.query_id) == QueryStatus.error
        assert self.cache.get(f"{self.query_id}:status:message") == "oh dear!"

    def test_attach_in_progress(self):
        self.cache.put(
            f"{self.query_id}:status", QueryStatus.in_progress, expire_after_seconds=2
        )
        before = time.time()
        assert self.sync.attach(self.query_id) is False
        # Make sure that we waited for the query status to change,
        # which took +- 2 seconds seconds.
        assert time.time() - before > 1

    def test_attach_completed(self):
        self.cache.put(
            f"{self.query_id}:status",
            QueryStatus.completed,
            expire_after_seconds=2,
        )
        before = time.time()
        assert self.sync.attach(self.query_id) is True
        # Make sure that we did not sleep, because the
        # query was already completed.
        assert time.time() - before < 1
