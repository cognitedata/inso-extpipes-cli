import logging
import pprint
from pathlib import Path
from typing import Dict, Self

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteNotFoundError

from .. import __version__
from ..app_config import CommandMode, ExtpipesConfig
from ..app_container import ContainerSelector, init_container
from ..app_exceptions import ExtpipesConfigError


class CommandBase:
    def __init__(
        self,
        config_path: str,
        command: CommandMode,
        debug: bool,
        dry_run: bool,
        dotenv_path: str | Path | None = None,
    ):

        # validate and load config according to command-mode
        ContainerCls = ContainerSelector[command]
        self.container = init_container(ContainerCls, config_path=config_path, dotenv_path=dotenv_path)

        # logging is now configured
        logging.info(f"Starting CDF Extraction Pipelines version <v{__version__}> for command: <{command}>")

        # Pull the config out of the container
        self.extpipes_config: ExtpipesConfig = self.container.extpipes()
        logging.debug(f"Features from config.yaml or defaults:\n {self.extpipes_config.features}")

        self.naming_pattern = self.extpipes_config.features.naming_pattern
        self.default_contacts = self.extpipes_config.features.default_contacts

        self.client: CogniteClient = self.container.cognite_client()
        self.cdf_project = self.client.config.project
        self.data_sets_in_scope = {}  # will be filled in within `validate`

        logging.info(f"Successful connection to CDF client to project: '{self.cdf_project}'")

        self.dry_run = dry_run
        if self.dry_run:
            logging.warning("Starting Dry Run!")

    def validate_config(self) -> Self:
        """
        Validates the structure of the config file
          * Data Sets exist in CDF
          * RAW Databases exist in CDF
          * Creates RAW Tables if they don't exist
        """
        # Data Sets
        requested_data_set_external_ids = list(
            {pipeline.data_set_external_id for pipeline in self.extpipes_config.pipelines}
        )
        logging.debug(f"{requested_data_set_external_ids=}")

        try:
            # will throw exception if one or more of the data sets don't exist
            self.data_sets_in_scope = {
                _d.external_id: _d
                for _d in self.client.data_sets.retrieve_multiple(external_ids=requested_data_set_external_ids)
            }
        except CogniteNotFoundError as e:
            if e.not_found:
                msg = f"Missing Data Sets: {e.not_found}"
            else:
                msg = str(e)
            logging.error(msg)
            raise ExtpipesConfigError(msg)

        # return self for chaining
        return self

    def ensure_raw_tables(self):
        # RAW
        def find_missing(existing: Dict, target: Dict) -> Dict:
            missing = {}

            for key, value_list in target.items():
                # If the key exists in the existing dictionary, find the difference.
                # Otherwise, the entire value_list is missing.
                if key in existing:
                    missing_values = [v for v in value_list if v not in existing[key]]
                    if missing_values:
                        missing[key] = missing_values
                else:
                    missing[key] = value_list

            return missing

        # build dictionary of configured dbs:tables
        requested_raw_tables: Dict = {}
        for pipeline in self.extpipes_config.pipelines:
            for raw_table in pipeline.raw_tables:
                if raw_table.db_name in requested_raw_tables:
                    requested_raw_tables[raw_table.db_name].append(raw_table.table_name)
                else:
                    requested_raw_tables[raw_table.db_name] = [raw_table.table_name]
        # get existing dbs/tables into a dict for fast lookup
        cdf_dbs: Dict = {}
        for db_name in {_db.name for _db in self.client.raw.databases.list(limit=None)}:
            cdf_dbs[db_name] = [table.name for table in self.client.raw.tables.list(db_name=db_name, limit=None)]

        missing = find_missing(cdf_dbs, requested_raw_tables)
        if missing:
            logging.warning(f"## Detected missing RAW tables: {pprint.pformat(missing)}")
            for _db, _tables in missing.items():
                self.client.raw.tables.create(db_name=_db, name=_tables)
