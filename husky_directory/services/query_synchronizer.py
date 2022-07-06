import hashlib
import time
from contextlib import contextmanager
from enum import Enum

from pydantic import BaseModel

from husky_directory.app_config import CacheExpirationSettings
from husky_directory.services.object_store import ObjectStorageInterface


class QueryStatus(Enum):
    in_progress = "in_progress"
    completed = "completed"
    not_found = "not_found"
    error = "error"


class QuerySynchronizer:
    """
    This service class provides functionality to lock queries to a given
    processor (app worker), and other processes to subscribe to those results.
    When users give us a query that takes longer than they expect, they often
    will interrupt and retry the query.

    While this does not speed up the query in question, it does mean that
    subsequent retries while the initial request is still in process will
    cost essentially zero extra compute resources.
    """

    def __init__(
        self, object_store: ObjectStorageInterface, config: CacheExpirationSettings
    ):
        self.cache = object_store
        self.config = config

    def get_status(self, query_id: str) -> QueryStatus:
        return QueryStatus(
            self.cache.get(f"{query_id}:status") or QueryStatus.not_found
        )

    @contextmanager
    def lock(
        self,
        query_id: str,
    ):
        """
        This is a `with` context that creates a status lock for the
        given id, which is updated upon completion. Any attached
        processes waiting for the query to complete can then
        parse and return the results.

        If an error occurs in the calling code, the error message will
        be stored in the cache for traceability.

        use:
           sync = QuerySynchronizer(object_store, config)
           with sync.lock('foo'):
               result = do_processing_work()
               sync.cache.put('foo', result)
        """
        status_key = f"{query_id}:status"
        self.cache.put(
            status_key,
            QueryStatus.in_progress.value,
            expire_after_seconds=self.config.in_progress_status_expiration,
        )
        try:
            yield
            self.cache.put(
                status_key,
                QueryStatus.completed.value,
                expire_after_seconds=self.config.completed_status_expiration,
            )
        except Exception as e:
            self.cache.put(
                status_key,
                QueryStatus.error.value,
                expire_after_seconds=self.config.error_status_expiration,
            )
            self.cache.put(
                f"{status_key}:message",
                str(e),
                expire_after_seconds=self.config.error_message_expiration,
            )
            raise

    def attach(self, query_id: str) -> bool:
        """
        Returns True iff the query was found and now has results waiting,
        False otherwise. If the status is found to be in progress already,
        it will ping for a new status every second.

        Use:
           sync = QuerySynchronizer(...)
           if sync.attach('foo'):
               return ResultModel.parse_raw(sync.cache.get('foo'))
        """
        query_status = self.get_status(query_id)
        while query_status == QueryStatus.in_progress:
            time.sleep(1)
            query_status = self.get_status(query_id)

        return query_status == QueryStatus.completed

    @staticmethod
    def get_model_digest(query_model: BaseModel) -> str:
        """
        Creates a deterministic query id for a given input,
        which allows requests on many servers to share a
        query process.
        """
        return hashlib.md5(
            query_model.json(
                exclude_unset=True, exclude_none=True, by_alias=True
            ).encode("UTF-8")
        ).hexdigest()
