from enum import Enum
from typing import List, Optional

from cognite.client.data_classes import Asset, DataSet, Event, Label, Sequence, TimeSeries
from pydantic import Field

from .common.base_model import Model

# because within f'' strings no backslash-character is allowed
NEWLINE = "\n"


# mixin 'str' to 'Enum' to support comparison to string-values
# https://docs.python.org/3/library/enum.html#others
# https://stackoverflow.com/a/63028809/1104502
class YesNoType(str, Enum):
    yes = "yes"
    no = "no"


class CommandMode(str, Enum):
    DEPLOY = "deploy"
    # DELETE = "delete"
    # DIAGRAM = "diagram"


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


class ScheduleType(str, Enum):
    continuous = "Continuous"
    on_trigger = "On trigger"


class Contact(Model):
    name: Optional[str]
    email: Optional[str]
    role: Optional[str]
    send_notification: Optional[bool]


class Pipeline(Model):
    # mandatory
    schedule: ScheduleType | str
    # az-func, adf, db, pi, ...
    source: Optional[str]
    suffix: Optional[str]
    # None/On trigger/Continuous/cron regex
    contacts: Optional[List[Contact]] = Field(default_factory=list)
    skip_rawtable: Optional[bool] = False


class Rawtable(Model):
    rawtable_name: str
    short_name: Optional[str]
    pipelines: List[Pipeline]


class Rawdb(Model):
    rawdb_name: str
    dataset_external_id: str
    short_name: Optional[str]
    rawtables: List[Rawtable]


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

    rawdbs: List[Rawdb]
