from pathlib import Path

import pytest
from rich import print

from extpipes.app_config import CommandMode
from extpipes.app_container import (
    ContainerSelector,
    DeployCommandContainer,
    init_container,
)
from tests.constants import ROOT_DIRECTORY

print(ROOT_DIRECTORY)


def generate_deploy_config_01_is_valid_test_data():
    yield pytest.param(
        config := ROOT_DIRECTORY / "example/config-deploy-example-01.0.yml",
        ROOT_DIRECTORY / "example/.env_mock",
        id=config.name,
    )
    # add more configs to for testing
    # yield pytest.param(
    #     config := ROOT_DIRECTORY / "example/config-deploy-example-01.1.yml",
    #     ROOT_DIRECTORY / "example/.env_mock",
    #     id=config.name,
    # )


@pytest.mark.parametrize("example_file, dotenv_path", generate_deploy_config_01_is_valid_test_data())
def test_deploy_config_01_is_valid(example_file: Path, dotenv_path: Path):
    """
    This test is intended to ensure that the configuration examples are valid.
    If this test fails, please update the relevant configuration example.
    """
    ContainerCls = ContainerSelector[CommandMode.DEPLOY]
    container: DeployCommandContainer = init_container(ContainerCls, example_file, dotenv_path)

    print(container.extpipes())
    print(container.cognite_config())

    # must contain extpipes section
    assert container.extpipes()
    assert isinstance(container.extpipes().features.default_contacts, list)
    assert container.extpipes().features.extpipe_pattern is None
    assert isinstance(container.extpipes().pipelines, list)
    # must be able to instantiate a CogniteClient (even with mocked client/secret)
    assert container.cognite_client().config.project
