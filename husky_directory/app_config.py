import logging
import os
from typing import Dict, Type, TypeVar, Union

import yaml
from injector import Module, inject, provider, singleton
from pydantic import BaseSettings, Field, SecretStr

logger = logging.getLogger("app_config")


class ApplicationConfig(BaseSettings):
    """
    Base settings for the application. These can be provided by a dotenv file, environment variables, or directly
    during instantiation of this object. The exception is the `settings_dir`, which _must_ be provided; this is because
    the settings_dir must be calculated before being able to load configuration in the settings_dir, which is needed to
    create instances of the ApplicationConfig object.

    Uses:
        # Explicitly declared settings
        ApplicationConfig(uwca_cert_name='foo', uwca_cert_path='/Users/me', pws_host='https://pws.uw.edu',
                          stage='development', settings_dir='/foo/settings')

        # Loaded from a .dotenv file:
        ApplicationConfig(_env_file='/foo/settings/blah.dotenv', settings_dir='/foo/settings')

        # Loaded entirely from environment variables:
        ApplicationConfig(settings_dir='/foo/settings')
    """

    settings_dir: str

    uwca_cert_name: str = Field(..., env="UWCA_CERT_NAME")
    uwca_cert_path: str = Field(..., env="UWCA_CERT_PATH")
    pws_host: str = Field(..., env="PWS_HOST")
    pws_default_path: str = Field(..., env="PWS_DEFAULT_PATH")
    stage: str = Field(..., env="FLASK_ENV")

    @property
    def uwca_certificate_path(self):
        return os.path.join(self.uwca_cert_path, f"{self.uwca_cert_name}.crt")

    @property
    def uwca_certificate_key(self):
        return os.path.join(self.uwca_cert_path, f"{self.uwca_cert_name}.crt")


class ApplicationConfigInjectorModule(Module):
    @provider
    @singleton
    def provide_application_config(self) -> ApplicationConfig:
        """
        Creates a singleton instance of the application config using the
        APP_DOTENV_FILE and APP_SETTINGS_DIR environment variables.
        Note that the default (and desired!) behavior is to allow environment variables to override settings loaded
        from APP_DOTENV_FILE.
        """
        # Before we do anything else, we load some bootstrapping environment variables to tell us
        # how to load the rest of our settings.
        settings_dir = os.environ.get(
            "APP_SETTINGS_DIR",
            default=os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "settings"
            ),
        )
        settings_file = os.environ.get("APP_DOTENV_FILE", "base.dotenv")
        settings_file_path = os.path.join(settings_dir, settings_file)
        return ApplicationConfig(
            _env_file=settings_file_path, settings_dir=settings_dir
        )


# NOT YET USED
class ApplicationSecrets(BaseSettings):
    # These should only be set in a deployed environment's gcp-k8 configuration
    # For more info, see: https://github.com/UWIT-IAM/gcp-docs/blob/master/secrets.md
    prometheus_username: SecretStr = Field(..., env="PROMETHEUS_USERNAME")
    prometheus_password: SecretStr = Field(..., env="PROMETHEUS_PASSWORD")


SettingsType = TypeVar(
    "SettingsType", bound=BaseSettings
)  # Used to type hint the return value of load_settings below


@singleton
class YAMLSettingsLoader:
    """
    Complex configuration is hard to express as environment variables; so, for everything else, there's YAML.
    YAML files loaded this way expect stage-based configuration.

    Here is an example of a simple YAML file:
        # foo.yml

        base: &base
            foo: bar
            baz: boop

        development: &development
            <<: *base  # Development uses all values from base

        eval: &eval  # Eval uses all settings from development, but overrides the 'baz' setting.
            <<: *development
            baz: snap

        special:  # Here is a special one-off stage that doesn't use anyone else's values
            foo: blah
            baz: also blah

        prod:
            <<: *eval
            foo: AH!

    The above configuration could be modeled and loaded:

        class FooSettings:
            foo: str
            baz: str

        settings = loader.load_settings('foo', output_type=FooSettings)
        settings.foo  # 'bar'

        settings = loader.load_settings('foo')
        settings['foo']  # 'bar'
    """

    @inject
    def __init__(self, app_config: ApplicationConfig):
        self.app_config = app_config

    @property
    def settings_dir(self) -> str:
        return self.app_config.settings_dir

    def load_settings(
        self,
        settings_name: str,
        output_type: Union[Type[SettingsType], Type[Dict]] = Dict,
    ) -> Union[Dict, SettingsType]:
        """
        Given a configuration name, looks up the setting file from ApplicationConfig.settings_dir,
        and loads the stage declared by ApplicationConfig.stage

        If no output type is provided, the results will be in dict form.
        """
        filename = os.path.join(self.settings_dir, f"{settings_name}.yml")
        stage = self.app_config.stage
        with open(filename) as f:
            try:
                settings = yaml.load(f, yaml.SafeLoader)[stage]
            except KeyError as e:
                raise KeyError(
                    f"{filename} has no configuration for stage '{stage}': {str(e)}"
                )

        if output_type is Dict:
            return settings
        return output_type.parse_obj(settings)
