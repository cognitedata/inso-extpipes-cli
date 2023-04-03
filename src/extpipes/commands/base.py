import logging
from typing import TypeVar

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteNotFoundError

from .. import __version__
from ..app_config import CommandMode, ExtpipesConfig
from ..app_container import ContainerSelector, init_container
from ..app_exceptions import ExtpipesConfigError

# '''
#  888888b.                     888             888                              .d8888b.
#  888  "88b                    888             888                             d88P  Y88b
#  888  .88P                    888             888                             888    888
#  8888888K.   .d88b.   .d88b.  888888 .d8888b  888888 888d888 8888b.  88888b.  888         .d88b.  888d888 .d88b.
#  888  "Y88b d88""88b d88""88b 888    88K      888    888P"      "88b 888 "88b 888        d88""88b 888P"  d8P  Y8b
#  888    888 888  888 888  888 888    "Y8888b. 888    888    .d888888 888  888 888    888 888  888 888    88888888
#  888   d88P Y88..88P Y88..88P Y88b.       X88 Y88b.  888    888  888 888 d88P Y88b  d88P Y88..88P 888    Y8b.
#  8888888P"   "Y88P"   "Y88P"   "Y888  88888P'  "Y888 888    "Y888888 88888P"   "Y8888P"   "Y88P"  888     "Y8888
#                                                                      888
#                                                                      888
#                                                                      888
# '''

# type-hint for BootstrapCommandBase instance response
T_CommandBase = TypeVar("T_CommandBase", bound="CommandBase")


class CommandBase:
    def __init__(self, config_path: str, command: CommandMode, debug: bool, dry_run: bool):
        logging.info(f"Starting CDF Extraction Pipelines version <v{__version__}> for command: <{command}>")

        # validate and load config according to command-mode
        ContainerCls = ContainerSelector[command]
        self.container: ContainerCls = init_container(ContainerCls, config_path)

        # Pull the config out of the container
        self.extpipes_config: ExtpipesConfig = self.container.extpipes()
        logging.debug(
            f"Features from config.yaml or defaults (can be overridden by cli-parameters!):\n {self.extpipes_config.features}"
        )

        self.extpipe_pattern: bool = self.extpipes_config.features.extpipe_pattern
        self.default_contacts: bool = self.extpipes_config.features.default_contacts

        self.client: CogniteClient = self.container.cognite_client()
        self.cdf_project = self.client.config.project

        logging.info(f"Successful connection to CDF client to project: '{self.cdf_project}'")

        self.dry_run = dry_run
        if self.dry_run:
            logging.warning("Starting Dry Run! Only Database tables will be created if configured.")

    def validate_config(self) -> T_CommandBase:
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
