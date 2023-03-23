import logging
import re
from datetime import datetime
from functools import lru_cache, partial
from typing import Any, Dict, List, Set, Tuple, TypeVar, Union

import yaml
from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteNotFoundError

from .. import __version__
from ..app_config import NEWLINE, CommandMode, ExtpipesConfig, YesNoType, supported_resource_types
from ..app_container import ContainerSelector, init_container
from ..app_exceptions import ExtpipesValidationError

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
    def __init__(self, config_path: str, command: CommandMode, debug: bool):

        # validate and load config according to command-mode
        ContainerCls = ContainerSelector[command]
        self.container: ContainerCls = init_container(ContainerCls, config_path)

        self.is_dry_run: bool = False
        self.client: CogniteClient = None
        self.cdf_project = None

        logging.info(f"Starting CDF Bootstrap version <v{__version__}> for command: <{command}>")

        # init command-specific parts
        # if subclass(ContainerCls, CogniteContainer):
        if command in (CommandMode.DEPLOY,):
            #
            # Cognite initialisation
            #
            self.client: CogniteClient = self.container.cognite_client()
            # TODO: support: token_custom_args
            # client_name="inso-bootstrap-cli", token_custom_args=self.config.token_custom_args

            self.cdf_project = self.client.config.project
            logging.info(f"Successful connection to CDF client to project: '{self.cdf_project}'")

        # not perfect refactoring yet, to handle the config loading for the different CommandMode-s
        match command:
            case CommandMode.DEPLOY:

                # TODO: correct for DIAGRAM and PREPARE?!
                self.extpipes_config: ExtpipesConfig = self.container.extpipes()

                #
                # load 'bootstrap.features'
                #
                # unpack and process features
                features = self.extpipes_config.features

                # TODO: not available for 'delete' but there must be a smarter solution
                logging.debug(
                    "Features from config.yaml or defaults (can be overridden by cli-parameters!): " f"{features=}"
                )

                # [OPTIONAL] default: False
                self.automatic_delete: bool = features.automatic_delete
                # [OPTIONAL] default: True
                self.extpipe_pattern: bool = features.extpipe_pattern
                # [OPTIONAL] default: False
                self.default_contacts: bool = features.default_contacts

    def dry_run(self, dry_run: YesNoType) -> T_CommandBase:
        self.is_dry_run = dry_run == YesNoType.yes

        if self.is_dry_run:
            logging.info("DRY-RUN active: No changes will be made to CDF")

        # return self for command chaining
        return self

    @lru_cache(maxsize=100)
    def resolve_external_id(
        self, resource_type: str, external_id: str, ignore_unknown_ids: bool = False
    ) -> Union[str, None]:

        logging.debug(f"resolve {resource_type=} {external_id=}")

        assert resource_type in supported_resource_types, f"Not supported resource_type= {resource_type}"
        resource = getattr(self.client, resource_type).retrieve(external_id=external_id)
        if resource:
            return resource.id
        elif ignore_unknown_ids:
            return None
        else:
            raise CogniteNotFoundError(not_found=[external_id])

    """
    ### validate config
    * dataset exists, if not fail
    * raw db exists, if not fail
    * raw table exists, if not create
    """

    def validate_config(self) -> T_CommandBase:

        # apply list(set()) to remove duplicates
        requested_rawdb_tables = list(
            set(
                [
                    (rawdb.rawdb_name, rawtable.rawtable_name)
                    for rawdb in self.config.rawdbs
                    for rawtable in rawdb.rawtables
                    # only request raw_table if
                    # if at least one pipeline is configured with 'skip-rawtable: false'
                    # all() returns False if at least one element is False
                    if not all([pipeline.skip_rawtable for pipeline in rawtable.pipelines])
                ]
            )
        )

        requested_data_set_external_ids = list(set([rawdb.dataset_external_id for rawdb in self.config.rawdbs]))

        logging.info(f"{requested_rawdb_tables=}")
        logging.info(f"{requested_data_set_external_ids=}")

        resolved_external_ids = list(
            filter(partial(self.resolve_external_id, "data_sets"), requested_data_set_external_ids)
        )
        assert set(requested_data_set_external_ids) == set(
            resolved_external_ids
        ), f"Data Sets missing: {set(requested_data_set_external_ids) - set(resolved_external_ids)}"

        """
        As we need to validate (db, table) tuples by comparing "requested vs existing",
        in case of a rawdb w/o tables, a dummy entry will be created:
        ```
        ('src:007:cargo:rawdb:state', 'n/a'),
        ```
        """
        # get existing dbs/tables
        existing_db_tables = [
            (db.name, (table.name if table is not None else "n/a"))
            for db in self.client.raw.databases.list(limit=None)
            # loop through a dummy None table, in case of empty
            for table in (self.client.raw.tables.list(db_name=db.name, limit=None) or [None])
        ]

        # missing dbs are a failure in our dataops approach, as all must be precreated
        assert set([r[0] for r in requested_rawdb_tables]).issubset(
            set([r[0] for r in existing_db_tables])
        ), f"RAW DBs missing: {set([r[0] for r in requested_rawdb_tables]) - set([r[0] for r in existing_db_tables])}"
        logging.info("All RAW DBs exist")
        # missing dbs exist
        # missing_raw_dbs = list(set([r[0] for r in requested_rawdb_tables]) - set([r[0] for r in existing_db_tables]))

        # missing tables can be created, so no assert
        # assert set(requested_rawdb_tables).issubset(set(existing_db_tables)),
        #   f'RAW Tables missing: {set(requested_rawdb_tables) - set(existing_db_tables)}'

        # validate tables exist
        missing_raw_tables = list(set(requested_rawdb_tables) - set(existing_db_tables))
        logging.info(f"missing_raw_tables= {missing_raw_tables}")

        created_tables = [
            self.client.raw.tables.create(db_name=db_name, name=table_name)
            for db_name, table_name in missing_raw_tables
        ]
        if len(created_tables):
            logging.info(f"{len(created_tables)} missing RAW tables created")

        # return self for chaining
        return self
