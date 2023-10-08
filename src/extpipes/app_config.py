import logging
from enum import ReprEnum  # new in 3.11
from typing import Optional, Dict, Set, Annotated

from jinja2 import Environment, meta
from pydantic import Field, model_validator, StringConstraints, field_validator
from pydantic_core.core_schema import ValidationInfo

from .common.base_model import Model


class CommandMode(str, ReprEnum):
    DEPLOY = "deploy"
    # DELETE = "delete"
    # DIAGRAM = "diagram"


CRON_OR_FIXED_PATTERN = (
    r"^(On trigger|Continuous)|"
    r"(@(annually|yearly|monthly|weekly|daily|hourly|reboot))|"
    r"(@every (\d+(ns|us|µs|ms|s|m|h))+)|"
    r"((((\d+,)+\d+|(\d+([/\-])\d+)|\d+|\*(/\d+)?) ?){5,7})$"
)


class Contact(Model):
    name: str
    email: str
    role: str
    send_notification: bool  # cognite-sdk doesn't use snake-case for this param


class RawTable(Model):
    db_name: str
    table_name: str


class Pipeline(Model):
    external_id: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    data_set_external_id: str
    schedule: Annotated[str, StringConstraints(pattern=CRON_OR_FIXED_PATTERN)]
    contacts: list[Contact] = Field(default=list())
    source: Optional[str] = Field(default=None)
    metadata: Dict[str, str] = Field(default=dict())
    documentation: Optional[str] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    raw_tables: list[RawTable] = Field(default=list())
    extpipe_config: Optional[Dict[str, str]] = Field(default=None)

    @field_validator('external_id', 'name')
    @classmethod
    def validate_field_length(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v and len(v) > 255:
            logging.warning(f'## {info.field_name} is longer than 255 characters and will be truncated: {v}')
        return v[:255] if v else None


class ExtpipesFeatures(Model):
    # jinja2 template to fill in both external_id and name
    naming_pattern: str = Field(default="")

    # load_yaml includes mapping from several string like 'yes|no' to boolean
    automatic_delete: bool = Field(default=False)

    # with default values must come last
    default_contacts: list[Contact] = Field(default=list())


class ExtpipesConfig(Model):
    """
    Configuration parameters for CDF Project Bootstrap, create mode
    """

    # here goes the main configuration
    features: ExtpipesFeatures = Field(
        default=ExtpipesFeatures(
            naming_pattern="",
            automatic_delete=False,
            default_contacts=[],
        )
    )

    pipelines: list[Pipeline]

    @model_validator(mode='after')
    def check_pattern_condition(self) -> 'ExtpipesConfig':
        if self.features.naming_pattern:
            misconfigured = [_pipeline.external_id for _pipeline in self.pipelines if _pipeline.external_id]
            if misconfigured:
                logging.error(f"## Misconfigured pipelines external_id: {misconfigured}")
                raise ValueError('With pattern provider, pipelines should not have external_id defined.')

            misconfigured = [_pipeline.name for _pipeline in self.pipelines if _pipeline.name]
            if misconfigured:
                logging.error(f"## Misconfigured pipelines name: {misconfigured}")
                raise ValueError('With pattern provider, pipelines should not have names defined.')

            def extract_jinja_variables(template: str) -> Set[str]:
                env = Environment()
                parsed_content = env.parse(template)
                # Extract all variables from the parsed content
                variables = meta.find_undeclared_variables(parsed_content)

                return variables

            required_fields = extract_jinja_variables(self.features.naming_pattern)

            misconfigured = [
                _pipeline.name
                for _pipeline in self.pipelines
                if not required_fields.issubset(_pipeline.metadata.keys())
            ]

            if len(misconfigured) > 0:
                logging.info(f"## Required metadata properties: {required_fields}")
                logging.error(f"## Misconfigured pipelines. Required metadata properties are required: {misconfigured}")
                raise ValueError('With pattern provider, pipelines should have respective metadata fields configured.')

        return self
