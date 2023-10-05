import logging
from typing import Self, TypeVar

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteNotFoundError

from .. import __version__
from ..app_config import CommandMode, ExtpipesConfig
from ..app_container import ContainerSelector, init_container
from ..app_exceptions import ExtpipesConfigError, ExtpipesValidationError


class CommandBase:
    def __init__(self, config_path: str, command: CommandMode, debug: bool, dry_run: bool):
        logging.info(f"Starting CDF Extraction Pipelines version <v{__version__}> for command: <{command}>")

        # validate and load config according to command-mode
        ContainerCls = ContainerSelector[command]
        self.container = init_container(ContainerCls, config_path)

        # Pull the config out of the container
        self.extpipes_config: ExtpipesConfig = self.container.extpipes()
        logging.debug(f"Features from config.yaml or defaults:\n {self.extpipes_config.features}")

        # 'features' defaults are set in the model
        assert self.extpipes_config.features
        assert self.extpipes_config.features.extpipe_pattern
        assert self.extpipes_config.features.default_contacts

        self.extpipe_pattern = self.extpipes_config.features.extpipe_pattern
        self.default_contacts = self.extpipes_config.features.default_contacts

        self.client: CogniteClient = self.container.cognite_client()
        self.cdf_project = self.client.config.project

        logging.info(f"Successful connection to CDF client to project: '{self.cdf_project}'")

        self.dry_run = dry_run
        if self.dry_run:
            logging.warning("Starting Dry Run! Only Database tables will be created if configured.")

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
            self.client.data_sets.retrieve_multiple(external_ids=requested_data_set_external_ids)
        except CogniteNotFoundError as e:
            if e.not_found:
                msg = f"Missing Data Sets: {e.not_found}"
            else:
                msg = e
            logging.error(msg)
            raise ExtpipesConfigError(msg)

        # RAW
        # build dictionary of configured dbs:tables
        requested_raw_tables = {}
        for pipeline in self.extpipes_config.pipelines:
            for raw_table in pipeline.raw_tables:
                if raw_table.db_name in requested_raw_tables:
                    requested_raw_tables[raw_table.db_name].append(raw_table.table_name)
                else:
                    requested_raw_tables[raw_table.db_name] = [raw_table.table_name]

        # get existing dbs/tables into a dict for fast lookup
        cdf_dbs = {db.name: [] for db in self.client.raw.databases.list(limit=None)}
        for db_name in cdf_dbs:
            # Calling .tables() on a Database object does this same thing anyways
            for table in self.client.raw.tables.list(db_name=db_name, limit=None):
                cdf_dbs[db_name].append(table.name)

        # check if all requested dbs and tables exist
        for req_db, req_tables in requested_raw_tables.items():
            if req_db not in cdf_dbs:
                logging.error(f"Missing '{req_db}' database")
                raise ExtpipesConfigError

            for req_table in req_tables:
                if req_table not in cdf_dbs[req_db]:
                    logging.warning(f"Missing {req_table} table in {req_db} database")

                    res = self.client.raw.tables.create(db_name=req_db, name=req_table)

                    logging.info(f"Created {res.name} table in {req_db} database")

        # return self for chaining
        return self
