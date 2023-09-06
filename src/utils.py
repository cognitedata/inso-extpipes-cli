import logging
import logging.config
from functools import lru_cache
from inspect import signature

from cognite.client import ClientConfig, CogniteClient
from cognite.client.config import global_config
from cognite.client.credentials import OAuthClientCredentials
from pydantic import constr

# Pydantic fields
NonEmptyString = constr(min_length=1, strip_whitespace=True)


@lru_cache(None)
def create_oidc_client(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    cdf_cluster: str,
    cdf_project: str,
) -> CogniteClient:
    global_config.disable_pypi_version_check = True
    return CogniteClient(
        ClientConfig(
            client_name="function-action-oidc",
            base_url=f"https://{cdf_cluster}.cognitedata.com",
            project=cdf_project,
            credentials=OAuthClientCredentials(
                token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=[f"https://{cdf_cluster}.cognitedata.com/.default"],
            ),
        )
    )


def create_oidc_client_from_dict(dct) -> CogniteClient:
    return create_oidc_client(
        **{k: dct[k] for k in signature(create_oidc_client).parameters}
    )


def setup_logging(run_debug_mode: bool = False):
    if run_debug_mode:
        logging.config.dictConfig(
            {
                "version": 1,
                "formatters": {
                    "formatter": {
                        "format": "[%(asctime)s] [%(levelname)s] : %(message)s"
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG",
                        "formatter": "formatter",
                        "stream": "ext://sys.stderr",
                    },
                },
                "root": {"level": "DEBUG", "handlers": ["console"]},
            }
        )
    else:
        logging.config.dictConfig(
            {
                "version": 1,
                "formatters": {
                    "formatter": {
                        "format": "[%(asctime)s] [%(levelname)s] : %(message)s"
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "formatter",
                        "stream": "ext://sys.stderr",
                    },
                },
                "root": {"level": "INFO", "handlers": ["console"]},
            }
        )
