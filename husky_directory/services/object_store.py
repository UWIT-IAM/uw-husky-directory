import json
import time
from abc import ABC, abstractmethod
from copy import copy
from enum import Enum
from typing import Any, Optional

from flask_injector import request
from injector import Module, provider
from pydantic import BaseModel
from redis import Redis

from husky_directory.app_config import ApplicationConfig
from husky_directory.util import AppLoggerMixIn


class ObjectStorageInterface(AppLoggerMixIn, ABC):
    """
    Basic interface that does nothing but declare
    abstractions.

    It also provides a utility method that can convert
    anything* into a string.

    *if the thing you want to convert can't be converted,
     add a case in the normalize_object_data implementation below.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        return None

    @abstractmethod
    def put(self, key: str, obj: Any, expire_after_seconds: Optional[int] = None):
        pass

    @staticmethod
    def normalize_object_data(obj: Any) -> str:
        if isinstance(obj, BaseModel):
            return obj.json()
        if isinstance(obj, Enum):
            obj = obj.value
        if not isinstance(obj, str):
            return json.dumps(obj)
        return obj


class InMemoryObjectStorage(ObjectStorageInterface):
    """
    Used when testing locally using flask itself,
    cannot be shared between processes. This is a very
    basic implementation which checks for key expiration
    on every `put`.
    """

    def __init__(self):
        self.__store__ = {}
        self.__key_expirations__ = {}

    def validate_key_expiration(self, key: str):
        expiration = self.__key_expirations__.get(key)
        now = time.time()
        if expiration:
            max_elapsed = expiration["max"]
            if not max_elapsed:
                return
            elapsed = now - expiration["stored"]
            if elapsed > max_elapsed:
                del self.__key_expirations__[key]
                if key in self.__store__:
                    del self.__store__[key]

    def expire_keys(self):
        for key in copy(self.__key_expirations__):
            self.validate_key_expiration(key)

    def get(self, key: str) -> Optional[str]:
        self.validate_key_expiration(key)
        return self.__store__.get(key)

    def put(self, key: str, obj: Any, expire_after_seconds: Optional[int] = None):
        self.expire_keys()
        self.__store__[key] = self.normalize_object_data(obj)
        now = time.time()
        self.__key_expirations__[key] = {"stored": now, "max": expire_after_seconds}
        return key


class RedisObjectStorage(ObjectStorageInterface):
    def __init__(self, redis: Redis, config: ApplicationConfig):
        self.redis = redis
        self.prefix = f"{config.redis_settings.namespace}:obj"

    def normalize_key(self, key: str) -> str:
        """Normalizes the key using the configured namespace."""
        if not key.startswith(self.prefix):
            key = f"{self.prefix}:{key}"
        return key

    def put(self, key: str, obj: Any, expire_after_seconds: Optional[int] = None):
        key = self.normalize_key(key)
        self.redis.set(key, self.normalize_object_data(obj), ex=expire_after_seconds)
        return key

    def get(self, key: str) -> Optional[str]:
        val = self.redis.get(self.normalize_key(key))
        if val:
            if isinstance(val, bytes):
                return val.decode("UTF-8")
            return val
        return None


class ObjectStoreInjectorModule(Module):
    @request
    @provider
    def provide_object_store(
        self, redis: Redis, config: ApplicationConfig
    ) -> ObjectStorageInterface:
        if config.redis_settings.host:
            return RedisObjectStorage(redis, config)
        return InMemoryObjectStorage()
