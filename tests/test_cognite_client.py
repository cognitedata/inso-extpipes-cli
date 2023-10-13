from pathlib import Path

import pytest
from dependency_injector import containers, providers
from rich import print

from extpipes.common.cognite_client import CogniteConfig


def test_cognite_config_02_is_valid():
    """
    This test is intended to ensure that the configuration examples are valid.
    If this test fails, please update the relevant configuration example.
    """

    # that's how dependecy-injector loaded the config from yaml with ennvar expansion
    config = {
        "host": "https://testfield.cognitedata.com/",
        "project": "shiny-prod",
        "idp-authentication": {
            "client-id": "111111-2222-3333-4444-55555555",
            "secret": "34534asdfadsg4445",
            "scopes": ["https://testfield.cognitedata.com/.default"],
            "token_url": "https://login.microsoftonline.com/31415-9265-359/oauth2/v2.0/token",
        },
    }

    # eval directly
    cognite_config = CogniteConfig.model_validate(config)

    # or eval the dependency-injector way
    cognite_config = providers.Resource(CogniteConfig.model_validate, obj=config)
    print(cognite_config)
