import logging
import os
import secrets
import string
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, TypeVar, cast

from injector import Module, provider, singleton
from pydantic import BaseSettings, Field, SecretStr, validator

logger = logging.getLogger("app_config")


class SessionType(Enum):
    """Session interface types. See flask-session documentation for full list of possibilities."""

    redis = "redis"
    filesystem = "filesystem"


class FlaskConfigurationSettings(BaseSettings):
    """
    A base class to make it easier to translate environment variables to flask configuration
    settings.

    To do so, simply include `flask_config_key=FOO` in a Field definition for any model that inherits from this base
    class.

    Example:
        class MySettings(FlaskConfigurationSettings):
            my_string: str = Field(..., env='MY_STRING_ENV_VAR', flask_config_key='SECRET_KEY')

    Now setting the `MY_STRING_ENV_VAR` variable will, when the application starts, ensure that `SECRET_KEY` is set
    on the flask application.
    """

    class Config:
        # Optionally, you can provide variables via a dotenv file instead of relying on all variables to be set.
        # You can supply the DOTENV_FILE environment variable to set the location of which dotenv file to load.
        env_file = os.environ.get("DOTENV_FILE", ".env")

    @property
    def flask_config_values(self) -> Dict[str, Any]:
        """By default, returns an empty dict. Override this if you need to provide variables to
        flask that aren't an easy 1:1 translation using `flask_config_key` as described above. Anything returned
        here can be overridden by the environment itself. This dict becomes the "default" return for app_configuration.
        """
        return {}

    @property
    def app_configuration(self) -> Dict[str, Any]:
        """
        This property captures a flat key-value store of all application settings declared by this model
        or any submodels that inherit from FlaskConfigurationSettings.

        Example:

            class FooSettings(FlaskConfigurationSettings):
                bar: str = Field(42, flask_config_key='FOO_BAR')

            class ModuleSettings(FlaskConfigurationSettings:
               foo_settings: FooSettings
               baz: int = Field(..., flask_config_key='MODULE_BAZ')

            mod_settings = ModuleSettings(baz=24)
            print(mod_settings.app_configuration)
                { "FOO_BAR": 42, "MODULE_BAZ": 24 }
        """
        # If the instance has set any overrides that aren't natively included by
        # the 'flask_config_key' attribute, we'll ensure they are included too.
        results = self.flask_config_values

        for field in self.dict().keys():
            value = getattr(self, field)
            if isinstance(value, FlaskConfigurationSettings):
                results.update(value.app_configuration)
                continue
            field_config = self.__fields__[field].field_info.extra
            flask_key = field_config.get("flask_config_key")

            if (
                flask_key == "_env"
            ):  # If someone wants to use the same name as the environment variable
                flask_key = field_config["env"]

            if flask_key:
                if isinstance(value, Enum):
                    value = value.value
                results[flask_key] = value
        return results


class RedisSettings(FlaskConfigurationSettings):
    """
    Settings for connecting to redis.
    The redis namespace is also our username.
    """

    host: str = Field(None, env="REDIS_HOST")
    port: str = Field("6379", env="REDIS_PORT")
    namespace: str = Field(None, env="REDIS_NAMESPACE")
    password: SecretStr = Field(None, env="REDIS_PASSWORD")
    default_cache_expire_seconds: Optional[int] = Field(
        None, env="REDIS_CACHE_DEFAULT_EXPIRE_SECONDS"
    )

    @property
    def flask_config_values(self) -> Dict[str, Any]:
        # These are derived from more than one environment variable,
        # so are not configured via the flask_config_key.
        # see FlaskConfigurationSettings.flask_config_values
        return {
            "SESSION_KEY_PREFIX": f"{self.namespace}:session:",
            "SESSION_REDIS": f"{self.host}:{self.port}",
            "SESSION_PERMANENT": False,
        }


class SessionSettings(FlaskConfigurationSettings):
    cookie_name: str = Field(
        "edu.uw.directory.session", env="SESSION_COOKIE_NAME", flask_config_key="_env"
    )
    preferences_cookie_name: str = Field("edu.uw.directory.preferences")
    secret_key: SecretStr = Field(None, env="SECRET_KEY", flask_config_key="_env")
    lifetime_seconds: int = Field(
        600, env="PERMANENT_SESSION_LIFETIME", flask_config_key="_env"
    )
    session_type: SessionType = Field(
        SessionType.filesystem,
        env="FLASK_SESSION_TYPE",
        flask_config_key="SESSION_TYPE",
    )
    filesystem_path: Optional[str] = Field(
        # By default this uses the current working directory, which might be anywhere!
        "/tmp/flask_session",
        env="SESSION_FILE_DIR",
        flask_config_key="_env",
    )

    @validator("secret_key")
    def ensure_secret_key(cls, val: Optional[str]) -> str:
        """
        The secret key is always required. If it's not provided, it will be generated. This is usually fine as-is.
        In a load-balanced environment, this should be a stored, shared secret for all environment
        containers.
        """
        if val:
            return val
        characters = string.ascii_letters + string.digits
        return "".join(secrets.choice(characters) for _ in range(24))


class AuthSettings(FlaskConfigurationSettings):
    """Stores settings related to authentication and SSL."""

    uwca_cert_name: str = Field(..., env="UWCA_CERT_NAME")
    uwca_cert_path: str = Field(..., env="UWCA_CERT_PATH")
    saml_entity_id: str = Field(..., env="SAML_ENTITY_ID")
    saml_acs_path: str = Field(..., env="SAML_ACS_PATH")
    use_test_idp: bool = Field(False, env="USE_TEST_IDP")


class PWSSettings(FlaskConfigurationSettings):
    """Stores settings related to the PWS API."""

    pws_host: str = Field(..., env="PWS_HOST")
    pws_default_path: str = Field(..., env="PWS_DEFAULT_PATH")


class MetricsSettings(FlaskConfigurationSettings):
    metric_prefix: str = Field("uw-directory", env="PROMETHEUS_METRIC_PREFIX")


class ApplicationSecrets(BaseSettings):
    # These should only be set in a deployed environment's gcp-k8 configuration
    # For more info, see: https://github.com/UWIT-IAM/gcp-docs/blob/master/secrets.md
    prometheus_username: Optional[SecretStr] = Field(None, env="PROMETHEUS_USERNAME")
    prometheus_password: Optional[SecretStr] = Field(None, env="PROMETHEUS_PASSWORD")


class CacheExpirationSettings(BaseSettings):
    class Config:
        """
        Any of these settings can be tweaked by updating
        the environment variables in the gcp-k8 helm release
        for this app using this prefix (or in any environment
        running this app).

        e.g.: QUERY_CACHE_IN_PROGRESS_STATUS_EXPIRATION=60
        """

        env_prefix = "QUERY_CACHE_"

    # We should never expect a query to take more than
    # 5 minutes to complete. If a query has taken /that/ long,
    # we simply delete the lock. This can mean that if a
    # query does take longer than 5 minutes,
    # the next request for it will be allowed
    # to proceed in its own process.
    in_progress_status_expiration: int = 300  # Five minutes

    # We do not want to cache completed queries for very long, because
    # we want updates to user profiles to be reflected in
    # near real-time. But, we want the value to persist
    # long enough that if the user mashes the 'search' button
    # while their browser is rendering thousands of
    # entries as HTML, it'll still be there, and the results will
    # seem to come faster to the user the second time around.
    # Therefore, the value is 7.
    completed_status_expiration: int = 7

    # The error status expiration lets us check for and/or
    # alarm on issues directly, without relying on logs, if the
    # issue happens during the query process (which is the
    # most likely place for an issue to occur). Remembering that
    # if the query is re-attempted, its status will revert back to
    # 'in progress', there is not really a point to keeping these for
    # super long.
    error_status_expiration: int = 3600  # 1 hour

    # The error message expiration lasts longer so that event
    # responders can access the error messages that were logged
    # via the cache, instead of poring through logs, if necessary,
    # for easier investigation. However, this is only a minor
    # convenience, as the JSON logging will already contain a
    # lot of information.

    # To find errors in a redis cache, you can use the command:
    #   'keys *:status:message'
    #   to get a list of all relevant keys in the shared cache.
    error_message_expiration: int = 3600 * 24  # 24 hours


@singleton
class ApplicationConfig(FlaskConfigurationSettings):
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
    stage: str = Field(..., env="FLASK_ENV")
    version: Optional[str] = Field(None, env="HUSKY_DIRECTORY_VERSION")
    start_time: datetime = Field(datetime.now())
    deployment_id: Optional[str] = Field(None, env="DEPLOYMENT_ID")
    show_experimental: Optional[bool] = Field(None, env="SHOW_EXPERIMENTAL_FEATURES")

    # Aggregated Settings
    pws_settings: PWSSettings = PWSSettings()
    auth_settings: AuthSettings = AuthSettings()
    session_settings: SessionSettings = SessionSettings()
    redis_settings: RedisSettings = RedisSettings()
    metrics_settings: MetricsSettings = MetricsSettings()
    cache_expiration_settings: CacheExpirationSettings = CacheExpirationSettings()
    secrets: ApplicationSecrets = ApplicationSecrets()

    @validator("redis_settings")
    def validate_redis_settings(
        cls, redis_settings: Optional[RedisSettings], values: Dict
    ) -> Optional[RedisSettings]:
        """Ensures that, if redis is the selected session type, a redis setting object is created if it is not
        already passed in."""
        if (
            cast(SessionSettings, values.get("session_settings")).session_type
            == SessionType.redis
            and not redis_settings
        ):
            return RedisSettings()
        return redis_settings


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
        config = ApplicationConfig(
            _env_file=settings_file_path, settings_dir=settings_dir
        )
        return config


SettingsType = TypeVar(
    "SettingsType", bound=BaseSettings
)  # Used to type hint the return value of load_settings below
