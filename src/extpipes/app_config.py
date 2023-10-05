from enum import ReprEnum  # new in 3.11
from typing import Optional

from pydantic import Field

from .common.base_model import Model


class CommandMode(str, ReprEnum):
    DEPLOY = "deploy"
    # DELETE = "delete"
    # DIAGRAM = "diagram"


class ScheduleType(str, ReprEnum):
    continuous = "Continuous"
    on_trigger = "On trigger"


class Contact(Model):
    name: Optional[str]
    email: Optional[str]
    role: Optional[str]
    sendNotification: Optional[bool]  # cognite-sdk doesn't use snake-case for this param


class RawTable(Model):
    db_name: str
    table_name: str


class Pipeline(Model):
    external_id: str
    name: str
    description: Optional[str]
    data_set_external_id: str
    schedule: Optional[ScheduleType | str]
    contacts: Optional[list[Contact]] = Field(default_factory=list)
    source: Optional[str]
    metadata: Optional[dict[str, str]]
    documentation: Optional[str]
    created_by: Optional[str]
    raw_tables: Optional[list[RawTable]]
    extpipe_config: Optional[dict[str, str]]


class ExtpipesFeatures(Model):

    # not implemented yet, for self-documentation only
    extpipe_pattern: Optional[str]

    # load_yaml includes mapping from several string like 'yes|no' to boolean
    automatic_delete: Optional[bool]

    # with default values must come last
    default_contacts: Optional[list[Contact]]


class ExtpipesConfig(Model):
    """
    Configuration parameters for CDF Project Bootstrap, create mode
    """

    # here goes the main configuration
    features: Optional[ExtpipesFeatures] = Field(
        default=ExtpipesFeatures(
            extpipe_pattern="{source}:{rawdb-name}:{rawtable-name}:{suffix}",
            automatic_delete=False,
            default_contacts=[],
        )
    )

    pipelines: list[Pipeline]
