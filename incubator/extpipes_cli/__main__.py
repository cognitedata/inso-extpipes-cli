# changelog
# * 220202 pa: copied first version from incubator-dataops notebook
# # *220404 tu: addition to versions on init, added semantic release instead
# * 220217 pa: v2 with a config-schema rewrite
#     * all names are now values, which cannot be changed by 'load_yaml(..)' util
#     * not specifc to bootstrap-cli name-convention anymore
#     * support of 'default-contacts' list

# tobedone:
# - [x] logger.info() or print() or click.echo(click.style(..))
#     - [ ] logger debug support
# - [x] config for ExtractionPipelineContact (atm Peter Arwanitis)
# - [ ] make it clear what is not found (dataset in this case)
#     cognite.client.exceptions.CogniteNotFoundError: Not found: ['src:006:gdm']

# # dataops: external pipeline (`extpipes`) creation / deletion
# * this configuration driven approach builds on top of the "dataops:cdf-groups" approach

# * This approach uses stable Python SDK `client.extraction_pipeline`
#     * [SDK documentation](https://cognite-docs.readthedocs-hosted.com/projects/cognite-sdk-python/en/latest/cognite.html?highlight=experimental#extraction-pipelines}
#     * [API documentation](https://docs.cognite.com/api/v1/#tag/Extraction-Pipelines)

# ## to be done
# - [x] `CogniteClient` instance configuration using env-variables
# - [ ] cleanup of `imports`
# - [ ] cleanup of unused code(?)
# - [ ] validation of `schedule` values

# ## dependencies are validated
# * Dataset must exist
# * RAW DBs must exist
# * Missing RAW Tables will be created
# * `schedule` only supports: `On trigger | Continuous | <cron expression> | null`

import dataclasses
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

import click
import pandas as pd
import requests
import yaml
from click import Context
from cognite.client.data_classes import (
    Asset,
    DataSet,
    Event,
    ExtractionPipeline,
    ExtractionPipelineContact,
    ExtractionPipelineList,
    Label,
    Sequence,
    TimeSeries,
)
from cognite.client.exceptions import CogniteNotFoundError
from cognite.extractorutils.configtools import CogniteClient, CogniteConfig, LoggingConfig, load_yaml
from dotenv import load_dotenv

from incubator.extpipes_cli import __version__

_logger = logging.getLogger(__name__)

#
# LOAD configs
#

#
#        name: string [ 1 .. 140 ] characters
#  externalId: string [ 1 .. 255 ] characters
# description: string [ 1 .. 500 ] characters
#


# mixin 'str' to 'Enum' to support comparison to string-values
# https://docs.python.org/3/library/enum.html#others
# https://stackoverflow.com/a/63028809/1104502
class YesNoType(str, Enum):
    yes = "yes"
    no = "no"


class ScheduleType(str, Enum):
    continuous = "Continuous"
    on_trigger = "On trigger"


@dataclass
class Contact:
    name: Optional[str]
    email: Optional[str]
    role: Optional[str]
    send_notification: Optional[bool]


@dataclass
class Pipeline:
    # mandatory
    schedule: Union[ScheduleType, str]
    # az-func, adf, db, pi, ...
    source: Optional[str]
    suffix: Optional[str]
    # None/On trigger/Continuous/cron regex
    contacts: Optional[List[Contact]] = field(default_factory=list)
    skip_rawtable: Optional[bool] = False


@dataclass
class Rawtable:
    rawtable_name: str
    short_name: Optional[str]
    pipelines: List[Pipeline]


@dataclass
class Rawdb:
    rawdb_name: str
    dataset_external_id: str
    short_name: Optional[str]
    rawtables: List[Rawtable]


#
# Old
#
@dataclass
class ExtpipesConfig:
    """
    Configuration parameters for CDF Project Bootstrap, create mode
    """

    logger: LoggingConfig
    cognite: CogniteConfig

    # here goes the main configuration
    rawdbs: List[Rawdb]

    # not implemented yet, for self-documentation only
    extpipe_pattern: Optional[str]

    # load_yaml includes mapping from several string like 'yes|no' to boolean
    automatic_delete: Optional[bool]

    # with default values must come last
    default_contacts: Optional[List[Contact]]

    # optional for OIDC authentication
    token_custom_args: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Handle default optional field settings"""

        # check each property for None and set default value
        if self.automatic_delete is None:
            self.automatic_delete = True
        if self.default_contacts is None:
            self.default_contacts = field(default_factory=list)

    @classmethod
    def from_yaml(cls, filepath):
        try:
            with open(filepath) as file:
                return load_yaml(source=file, config_type=cls)
        except FileNotFoundError as exc:
            print("Incorrect file path, error message: ", exc)
            raise


class ExtpipesConfigError(Exception):
    """Exception raised for config parser

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


# type hints
External_ids = List[str]

# generic resolve_external_id approach
supported_resource_types = {
    "time_series": TimeSeries,
    "data_sets": DataSet,
    "events": Event,
    "sequences": Sequence,
    "assets": Asset,
    "labels": Label,
    "files": None,  # no data_class available for create(...)
}

# type-hint for ExtpipesCore instance response
T_ExtpipesCore = TypeVar("T_ExtpipesCore", bound="ExtpipesCore")


class ExtpipesCore:

    # client: CogniteClient
    # config: ExtpipesConfig

    def __init__(self, configpath: str):
        self.config: ExtpipesConfig = ExtpipesConfig.from_yaml(configpath)

        # print(f'{self.config=}')

        # make sure the optional folders in logger.file.path exists
        # to avoid: FileNotFoundError: [Errno 2] No such file or directory: '/github/workspace/logs/test-deploy.log'

        if self.config.logger.file:
            (Path.cwd() / self.config.logger.file.path).parent.mkdir(parents=True, exist_ok=True)

        self.config.logger.setup_logging()

        # [OPTIONAL] default: True
        self.automatic_delete: bool = self.config.automatic_delete

        _logger.info("Starting CDF Extpipes configuration")

        self.client: CogniteClient = self.config.cognite.get_cognite_client(
            client_name="inso-extpipes-cli", token_custom_args=self.config.token_custom_args
        )

    @lru_cache(maxsize=100)
    def resolve_external_id(
        self, resource_type: str, external_id: str, ignore_unknown_ids: bool = False
    ) -> Union[str, None]:

        _logger.debug(f"resolve {resource_type=} {external_id=}")

        assert resource_type in supported_resource_types, f"Not supported resource_type= {resource_type}"
        resource = getattr(self.client, resource_type).retrieve(external_id=external_id)
        if resource:
            return resource.id
        elif ignore_unknown_ids:
            return None
        else:
            raise CogniteNotFoundError(not_found=[external_id])

    def get_requested_dict(self) -> Dict[str, List[ExtractionPipeline]]:

        #
        # helper methods
        #
        def timestamp():
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # fixing E731 do not assign a lambda expression, use a def
        # timestamp = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # print(f"{timestamp()} It's DataOps time")

        def external_id_template(**kwargs):
            # pipeline: adf
            # group: src:002:internal
            # tableName: int_events (which needs split from optional suffix: int_events:hourly)

            # output:
            # adf:src:002:int_events
            external_id = f"{kwargs['pipeline'].source+':' if kwargs['pipeline'].source else ''}{kwargs['rawdb'].short_name or kwargs['rawdb'].rawdb_name}:{kwargs['rawtable'].short_name or kwargs['rawtable'].rawtable_name}{':'+kwargs['pipeline'].suffix if kwargs['pipeline'].suffix else ''}"
            assert len(external_id) < 140, f"name= {external_id} is too long (max 140 characters)"
            # assert len(external_id) < 255, f'external_id= {external_id} is too long'
            # _logger.info(external_id)
            return external_id

            # return f"{kwargs['pipeline']}:{':'.join(kwargs['group'].split(':')[:2])}:{kwargs['tableName']}"

        def description_template(**kwargs):
            # pipeline: adf
            # tableName: un_ports
            # output:
            # UN_PORTS integration through ADF
            description = f"{kwargs['rawtable'].rawtable_name.upper()} {'integration through ' + kwargs['pipeline'].source.upper() if kwargs['pipeline'].source else ''}"
            assert len(description) < 500, f"name= {description} is too long (max 500 characters)"
            # _logger.info(description)
            return description

        return {
            external_id_template(**locals()): ExtractionPipeline(
                external_id=external_id_template(**locals()),
                name=external_id_template(**locals()),
                # external dataset id has no `:dataset` suffix, but is simply the group name like `src:001:exact`
                data_set_id=self.resolve_external_id(
                    "data_sets", external_id=rawdb.dataset_external_id, ignore_unknown_ids=True
                ),
                description=description_template(**locals()),
                metadata={
                    "dataops_created": f"{timestamp()}",
                    "dataops_source": f"extpipe-config v{__version__}",
                },
                # [{"dbName": "value", "tableName" : "value"}]
                # following the incubator-dataops naming conventions
                raw_tables=(
                    [{"dbName": rawdb.rawdb_name, "tableName": rawtable.rawtable_name}]
                    if not pipeline.skip_rawtable
                    else []
                ),
                contacts=[
                    ExtractionPipelineContact(**dataclasses.asdict(contact))
                    for contact in (pipeline.contacts or self.config.default_contacts)
                ],
                # no validation yet
                schedule=pipeline.schedule,
            )
            for rawdb in self.config.rawdbs
            for rawtable in rawdb.rawtables
            for pipeline in rawtable.pipelines
        }

    """
    ### validate config
    * dataset exists, if not fail
    * raw db exists, if not fail
    * raw table exists, if not create
    """

    def validate_config(self) -> T_ExtpipesCore:

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

        _logger.info(f"{requested_rawdb_tables=}")
        _logger.info(f"{requested_data_set_external_ids=}")

        resolved_external_ids = list(
            filter(partial(self.resolve_external_id, "data_sets"), requested_data_set_external_ids)
        )
        assert set(requested_data_set_external_ids) == set(
            resolved_external_ids
        ), f"Data Sets missing: {set(requested_data_set_external_ids) - set(resolved_external_ids)}"

        """
        As we need to validate (db, table) tuples by comparing "requested vs existing", in case of a rawdb w/o tables, a dummy entry will be created:
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
        _logger.info("All RAW DBs exist")
        # missing dbs exist
        # missing_raw_dbs = list(set([r[0] for r in requested_rawdb_tables]) - set([r[0] for r in existing_db_tables]))

        # missing tables can be created, so no assert
        # assert set(requested_rawdb_tables).issubset(set(existing_db_tables)), f'RAW Tables missing: {set(requested_rawdb_tables) - set(existing_db_tables)}'

        # validate tables exist
        missing_raw_tables = list(set(requested_rawdb_tables) - set(existing_db_tables))
        _logger.info(f"missing_raw_tables= {missing_raw_tables}")

        created_tables = [
            self.client.raw.tables.create(db_name=db_name, name=table_name)
            for db_name, table_name in missing_raw_tables
        ]
        if len(created_tables):
            _logger.info(f"{len(created_tables)} missing RAW tables created")

        # return self for chaining
        return self

    """
    ### create / delete
    * new in config
    * delete removed from config

    Only extpipes get managed (and deleted) which were created with metadata containing `dataops_created`
    Manually created extpipes are not affected by this approach
    """

    def deploy(self, automatic_delete: YesNoType):

        # check click parameter and map from YesNoType to bool
        # if provided they override configuration or defaults from yaml-config
        if automatic_delete:
            self.automatic_delete = automatic_delete == YesNoType.yes

        # get existing extpipes
        """
        ### list and inspect existing extpipes
        """
        existing_extpipes = self.client.extraction_pipelines.list(limit=None)
        # existing_extpipes[:2]

        existing_extpipes_dict = {ep.external_id: ep for ep in existing_extpipes}

        def get_new_ids(requested_ids: External_ids, existing_ids: External_ids) -> External_ids:
            return list(set(requested_ids) - set(existing_ids))

        def get_delete_ids(requested_ids: External_ids, existing_ids: External_ids) -> External_ids:
            return list(set(existing_ids) - set(requested_ids))

        # get existing -unused
        """
        existing_dict = {
            ep.external_id: ep
            for ep in self.client.extraction_pipelines.list(limit=-1)
            # only manage dataops created extpipes and not manually created
            # metadata can be None
            if "dataops_created" in (ep.metadata if ep.metadata else {})
        }
        """

        # get requested from config
        requested_dict = self.get_requested_dict()

        # debug
        # print('\n'.join([f'{i} : {k}' for i,k in enumerate(requested_dict.keys())]))
        # for i, (extpipe_name, extpipe) in enumerate(requested_dict.items()):
        #     print(i, extpipe_name, extpipe)

        new_ids: External_ids = get_new_ids(requested_dict.keys(), existing_extpipes_dict.keys())
        _logger.info("## extraction pipelines to create:")
        _logger.info(new_ids)

        delete_ids: External_ids = []
        if self.automatic_delete:
            # delete non specified (configured) extpipes, to keep the deployment in sync
            delete_ids = get_delete_ids(requested_dict.keys(), existing_extpipes_dict.keys())
            _logger.info("## extraction pipelines to delete:")
            _logger.info(delete_ids)

            self.client.extraction_pipelines.delete(external_id=delete_ids)
        else:
            _logger.info("## skipping automatic-delete: configuration deactivated")

        # updated = self.client.extraction_pipelines.update([ep for ep in transformations if ep.external_id in existing_ids])
        # created: ExtractionPipelineList = self.client.extraction_pipelines.create(
        #     [ep for external_id, ep in requested_dict.items() if external_id in new_ids]
        # )
        # xxx pa: switch to create extpipes one by one to bypass an issue
        created: ExtractionPipelineList = [
            self.client.extraction_pipelines.create(ep)
            for external_id, ep in requested_dict.items()
            if external_id in new_ids
        ]

        _logger.info(f"Extraction Pipelines: created: {len(created)}, deleted: {len(delete_ids)}")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(prog_name="extpipes_cli", version=__version__)
@click.option(
    "--cdf-project-name",
    help="Project to interact with transformations API, 'EXTPIPES_CDF_PROJECT' environment variable can be used instead. Required for OAuth2 and optional for api-keys.",
    envvar="EXTPIPES_CDF_PROJECT",
)
@click.option(
    "--cluster",
    default="westeurope-1",
    help="The CDF cluster where Transformations is hosted (e.g. greenfield, europe-west1-1). Provide this or make sure to set 'EXTPIPES_CDF_CLUSTER' environment variable.",
    envvar="EXTPIPES_CDF_CLUSTER",
)
@click.option(
    "--host",
    default="bluefield",
    help="The CDF cluster where Extraction-Pipelines are hosted (e.g. https://bluefield.cognitedata.com). Provide this or make sure to set 'EXTPIPES_CDF_HOST' environment variable.",
    envvar="EXTPIPES_CDF_HOST",
)
@click.option(
    "--api-key",
    help="API key to interact with transformations API. Provide this or make sure to set 'EXTPIPES_CDF_API_KEY' environment variable if you want to authenticate with API keys.",
    envvar="EXTPIPES_CDF_API_KEY",
)
@click.option(
    "--client-id",
    help="Client ID to interact with transformations API. Provide this or make sure to set 'EXTPIPES_IDP_CLIENT_ID' environment variable if you want to authenticate with OAuth2.",
    envvar="EXTPIPES_IDP_CLIENT_ID",
)
@click.option(
    "--client-secret",
    help="Client secret to interact with transformations API. Provide this or make sure to set 'EXTPIPES_IDP_CLIENT_SECRET' environment variable if you want to authenticate with OAuth2.",
    envvar="EXTPIPES_IDP_CLIENT_SECRET",
)
@click.option(
    "--token-url",
    help="Token URL to interact with transformations API. Provide this or make sure to set 'EXTPIPES_IDP_TOKEN_URL' environment variable if you want to authenticate with OAuth2.",
    envvar="EXTPIPES_IDP_TOKEN_URL",
)
@click.option(
    "--scopes",
    help="Scopes to interact with transformations API, relevant for OAuth2 authentication method. 'EXTPIPES_IDP_SCOPES' environment variable can be used instead.",
    envvar="EXTPIPES_IDP_SCOPES",
)
@click.option(
    "--audience",
    help="Audience to interact with transformations API, relevant for OAuth2 authentication method. 'EXTPIPES_IDP_AUDIENCE' environment variable can be used instead.",
    envvar="EXTPIPES_IDP_AUDIENCE",
)
@click.pass_context
def extpipes_cli(
    context: Context,
    cluster: str = "westeurope-1",
    host: str = None,
    api_key: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    token_url: Optional[str] = None,
    scopes: Optional[str] = None,
    audience: Optional[str] = None,
    cdf_project_name: Optional[str] = None,
) -> None:
    context.obj = {
        "cluster": cluster,
        "host": host,
        "api_key": api_key,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_url": token_url,
        "scopes": scopes,
        "audience": audience,
        "cdf_project_name": cdf_project_name,
    }


@click.command(help="Deploy a set of extpipes from a config-file")
@click.argument(
    "config_file",
    default="./config-extpipes.yml",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Print debug information",
)
@click.option(
    "--automatic-delete",
    # default="yes", # default defined in 'ExtpipesConfig'
    type=click.Choice(["yes", "no"], case_sensitive=False),
    help="Purge extpipes which are not specified in config-file automatically "
    "(this is the default behavior, to keep deployment in sync with configuration)",
)
@click.pass_obj
def deploy(obj: Dict, config_file: str, automatic_delete: YesNoType, debug: bool = False) -> None:

    click.echo(click.style("Deploying Extraction Pipelines...", fg="red"))

    if debug:
        # TODO not working yet :/
        _logger.setLevel("DEBUG")  # INFO/DEBUG

    try:
        # load .env from file if exists
        load_dotenv()

        # run deployment
        (ExtpipesCore(config_file).validate_config().deploy(automatic_delete=automatic_delete))

        click.echo(click.style("Extraction Pipelines deployed", fg="green"))

    except ExtpipesConfigError as e:
        exit(e.message)


extpipes_cli.add_command(deploy)


def main() -> None:
    # call click.pass_context
    extpipes_cli()


# extpipes_cli.add_command(deploy)

if __name__ == "__main__":
    main()
