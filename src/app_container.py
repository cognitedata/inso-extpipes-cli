import logging.config
from pathlib import Path
from typing import Dict, Optional

from dependency_injector import containers, providers
from dotenv import load_dotenv

from .app_config import CommandMode, ExtpipesConfig
from .common.cognite_client import CogniteConfig, get_cognite_client


def init_container(
    container_cls: containers.Container,
    config_path: str | Path = "/etc/f25e/config.yaml",
    dotenv_path: str | Path = None,
):
    """Spinning up container and

    Args:
        container_cls (containers.Container): support different
        config_path (str | Path, optional): _description_. Defaults to "/etc/f25e/config.yaml".
        dotenv_path (str | Path, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    # checks for .env file, loads it and override existing env-variables
    load_dotenv(dotenv_path, override=True)

    container = container_cls()
    container.config.from_yaml(config_path, required=True)
    container.init_resources()  # i.e.logging

    # logging.debug(f"{container.config()=}")

    return container


def init_logging(logging_config: Optional[Dict], deprecated_logger_config: Optional[Dict]):
    # https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
    # from logging-cookbook examples for 'logging_config' dict
    # TODO: needed to handle missing log folders?
    if logging_config:
        logging.config.dictConfig(logging_config)

        logging.debug(f"{logging_config=}")

    elif deprecated_logger_config:
        # convert extractorutils logger-config to a standard 'dictConfig'
        # TODO: deprecation warning
        logging.config.dictConfig(
            {
                "version": 1,
                "formatters": {"formatter": {"format": "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"}},
                "handlers": {
                    "file": {
                        "class": "logging.FileHandler",
                        "filename": deprecated_logger_config.get("file", {}).get("path", "./logs/extpipes.log"),
                        "formatter": "formatter",
                        "mode": "w",
                        "level": deprecated_logger_config.get("file", {}).get("level", "INFO"),
                    },
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": deprecated_logger_config.get("console", {}).get("level", "INFO"),
                        "formatter": "formatter",
                        "stream": "ext://sys.stderr",
                    },
                },
                "root": {"level": "DEBUG", "handlers": ["console", "file"]},
            }
        )
    else:
        # if no logging config given, make a simple one to console only
        logging.basicConfig(
            format="%(asctime)s [%(levelname)-8s] %(threadName)s - %(message)s",
            level=logging.INFO,
            handlers=[
                # logging.FileHandler("./logs/debug.log"),
                logging.StreamHandler()
            ],
        )

    yield logging.getLogger()


def shutdown_container(container):
    logging.debug("function to handle additional shutdown of resources")
    container.shutdown_resources()


class BaseContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            __name__,
            # ".app",
            # ".server",
            # ".tools",
        ],
    )
    config = providers.Configuration()

    # support old extractorutils LoggingConfig (console/file)
    logging = providers.Resource(init_logging, logging_config=config.logging, deprecated_logger_config=config.logger)


class CogniteContainer(BaseContainer):
    # provides config.cognite:dict as pydantic CogniteConfig object
    # and reveals all pydantic errors on container.init_resource
    cognite_config = providers.Resource(CogniteConfig.parse_obj, obj=BaseContainer.config.cognite)

    cognite_client = providers.Factory(
        get_cognite_client,
        cognite_config,
    )


class DeployCommandContainer(CogniteContainer):
    """Container providing 'cognite_client' and 'extpipes'

    Args:
        CogniteContainer (_type_): _description_
    """

    extpipes = providers.Resource(ExtpipesConfig.parse_obj, obj=CogniteContainer.config.extpipes)


ContainerSelector = {
    # CommandMode.PREPARE: DeployCommandContainer,
    # CommandMode.DIAGRAM: DiagramCommandContainer,
    CommandMode.DEPLOY: DeployCommandContainer,
    # CommandMode.DELETE: DeleteCommandContainer,
}
