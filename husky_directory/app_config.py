import os
import logging
import yaml

logger = logging.getLogger("app_config")


def get_settings_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(here, "settings")
    logging.info(f"Default settings directory is {default}")
    override = os.environ.get("APP_SETTINGS_DIR")
    logging.info(f"Settings directory override: {override}")
    return override or default


def get_log_config():
    filename = os.path.join(get_settings_dir(), "logging.yml")
    stage = os.getenv("FLASK_ENV", "development")
    with open(filename) as f:
        try:
            return yaml.load(f, yaml.SafeLoader)[stage]
        except KeyError as e:
            raise KeyError(f"{filename} has no configuration for {stage}: {str(e)}")
