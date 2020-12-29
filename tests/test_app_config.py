import os
from unittest import mock

import pytest
from injector import Injector

from husky_directory.app_config import (
    ApplicationConfig,
    ApplicationSecrets,
    YAMLSettingsLoader,
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
            "uwca_cert_path",
            "uwca_cert_name",
            "pws_host",
            "pws_default_path",
            "settings_dir",
            "stage",
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


class TestYAMLSettingsLoader:
    @pytest.fixture(autouse=True)
    def configure_base(self, injector: Injector, test_root_path: str):
        self.loader = injector.get(YAMLSettingsLoader)
        self.loader.app_config.settings_dir = os.path.join(test_root_path, "data")
        self.loader.app_config.stage = "development"

    def test_yaml_settings_loader(self):
        assert self.loader.load_settings("testconfig")["foo"] == "bar"

    def test_yaml_settings_loader_fails_wrong_stage(self):
        self.loader.app_config.stage = "error"
        with pytest.raises(KeyError):
            self.test_yaml_settings_loader()
