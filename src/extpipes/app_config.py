from enum import Enum
from typing import Dict, List, Optional

from cognite.client.data_classes import Asset, DataSet, Event, Label, Sequence, TimeSeries
from pydantic import Field

from .common.base_model import Model


class CommandMode(str, Enum):
    DEPLOY = "deploy"
    # DELETE = "delete"
    # DIAGRAM = "diagram"


class ScheduleType(str, Enum):
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
    contacts: Optional[List[Contact]] = Field(default_factory=list)
    source: Optional[str]
    metadata: Optional[Dict[str, str]]
    documentation: Optional[str]
    created_by: Optional[str]
    raw_tables: Optional[List[RawTable]]
    extpipe_config: Optional[Dict[str, str]]


class ExtpipesFeatures(Model):

    # not implemented yet, for self-documentation only
    extpipe_pattern: Optional[str]

    # load_yaml includes mapping from several string like 'yes|no' to boolean
    automatic_delete: Optional[bool]

    # with default values must come last
    default_contacts: Optional[List[Contact]]


class ExtpipesConfig(Model):
    """
    Configuration parameters for CDF Project Bootstrap, create mode
    """

    # here goes the main configuration
    features: Optional[ExtpipesFeatures] = Field(
        default=ExtpipesFeatures(
            **dict(
                extpipe_pattern="{source}:{rawdb-name}:{rawtable-name}:{suffix}",
                automatic_delete=False,
                default_contacts=[],
            )
        )
    )

    pipelines: List[Pipeline]
