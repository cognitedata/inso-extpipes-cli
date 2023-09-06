import logging
from pathlib import Path

import yaml

from configs import ConfigurationFile, DeployCredentials, ExtPipesConfig, RunConfig
from orchestrator import upsert_extraction_pipelines
from utils import setup_logging


def main(config: RunConfig):
    deploy_client = config.deploy_creds.client
    config_ext_pipes = config.extraction_pipelines

    upsert_extraction_pipelines(client=deploy_client, eps_config=config_ext_pipes)


def get_config_dict(path: Path):
    with open(path, "r") as yaml_file:
        data = yaml.safe_load(yaml_file)
    return data


if __name__ == "__main__":
    deploy_creds = DeployCredentials.from_envvars()
    config = ConfigurationFile.from_envvars()

    setup_logging(run_debug_mode=config.run_debug_mode)
    logging.info("Start Running Extraction Pipelines Orchestrator")

    config_dict = get_config_dict(Path(config.config_file_path))
    config_ext_pipes = ExtPipesConfig.model_validate(config_dict)

    logging.debug("Setup Run Configuration")
    run_config = RunConfig(
        deploy_creds=deploy_creds,
        extraction_pipelines=config_ext_pipes,
    )

    main(config=run_config)

    logging.info("Successfully completed running Extraction Pipelines Orchestrator")
