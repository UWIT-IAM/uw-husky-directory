import time
from typing import cast

import pytest
from pydantic import create_model
from redis import Redis

from husky_directory.app_config import ApplicationConfig
from husky_directory.services.object_store import (
    InMemoryObjectStorage,
    ObjectStorageInterface,
    RedisObjectStorage,
)
from husky_directory.services.query_synchronizer import QueryStatus


@pytest.mark.parametrize(
    "redis_host, expected_type",
    [
        (None, InMemoryObjectStorage),
        ("localhost", RedisObjectStorage),
    ],
)
def test_object_store_interface(injector, redis_host, expected_type):
    settings = injector.get(ApplicationConfig)
    settings.redis_settings.host = redis_host
    assert type(injector.get(ObjectStorageInterface)) == expected_type


@pytest.mark.parametrize(
    "obj, expected",
    [
        (True, "true"),
        (False, "false"),
        (QueryStatus.completed, "completed"),
        ({"foo": "bar"}, '{"foo": "bar"}'),
        (create_model("FooModel", foo=(str, "bar"))(), '{"foo": "bar"}'),
    ],
)
def test_normalize_object_data(obj, expected):
    assert ObjectStorageInterface.normalize_object_data(obj) == expected


def test_local_interface():
    store = InMemoryObjectStorage()
    store.put("foo", True, expire_after_seconds=1)
    assert store.get("foo") == "true"
    time.sleep(1.1)
    assert not store.get("foo")


class MockRedis(InMemoryObjectStorage):
    def set(self, key, val, ex=None):
        val = self.normalize_object_data(val)
        self.put(key, val, expire_after_seconds=ex)


def test_redis_interface(injector):
    mock_redis_ = MockRedis()
    cfg = injector.get(ApplicationConfig)
    cfg.redis_settings.namespace = "uw-directory"

    store = RedisObjectStorage(
        cast(Redis, mock_redis_),
        cfg,
    )
    store.put("hello", True, expire_after_seconds=None)
    assert "uw-directory:obj:hello" in mock_redis_.__store__
    assert store.get("hello") == "true"
