import os
from unittest import mock

import pytest
from injector import Injector

from husky_directory.app_config import (
    ApplicationConfig,
    ApplicationSecrets,
    RedisSettings,
)


class TestApplicationConfig:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector: Injector):
        self.injector = injector
        self.app_config = injector.get(ApplicationConfig)

    def test_app_config_is_singleton(self):
        assert id(self.app_config) == id(self.injector.get(ApplicationConfig))

    def test_app_config_has_fields(self):
        expected_field_names = {
            "settings_dir",
            "stage",
            "version",
            "start_time",
            "auth_settings",
            "redis_settings",
            "session_settings",
            "pws_settings",
            "deployment_id",
            "secrets",
            "metrics_settings",
            "show_experimental",
            "cache_expiration_settings",
        }
        assert set(self.app_config.dict().keys()) == expected_field_names


class TestApplicationSecrets:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector: Injector):
        self.injector = injector
        # These shouldn't be set in a normal test environment, so we'll set them here.
        with mock.patch.dict(os.environ) as mock_environ:
            mock_environ["PROMETHEUS_USERNAME"] = "promuser"
            mock_environ["PROMETHEUS_PASSWORD"] = "prompass"
            self.app_secrets = self.injector.get(ApplicationSecrets)
            yield

    def test_app_secrets_has_fields(self):
        expected_field_names = {"prometheus_username", "prometheus_password"}
        assert set(self.app_secrets.dict().keys()) == expected_field_names


class TestRedisSettings:
    def test_flask_config_values(self):
        settings = RedisSettings(host="redis", namespace="directory")
        assert settings.flask_config_values == {
            "SESSION_KEY_PREFIX": "directory:session:",
            "SESSION_REDIS": "redis:6379",
            "SESSION_PERMANENT": False,
        }
