from os import getenv
from typing import Optional

from cognite.client.data_classes import ExtractionPipeline, ExtractionPipelineConfig
from crontab import CronSlices
from pydantic import BaseModel, Field, validator

from utils import NonEmptyString, create_oidc_client_from_dict


class CredentialsModel(BaseModel):
    @property
    def credentials(self) -> dict[str, str]:
        return self.model_dump(include={"client_id", "client_secret"})

    @property
    def client(self):
        return create_oidc_client_from_dict(self.model_dump(by_alias=False))


class ActionModel(BaseModel):
    class Config:
        allow_population_by_field_name = True

    @classmethod
    def from_envvars(cls):
        """Magic parameter-load from env.vars. (Github Action Syntax)"""

        def get_parameter(key, prefix=""):
            # Missing args passed as empty strings, load as `None` instead:
            return getenv(f"{prefix}{key.upper()}", "").strip() or None

        expected_params = cls.model_json_schema()["properties"]
        return cls.model_validate(
            {
                k: v
                for k, v in zip(expected_params, map(get_parameter, expected_params))
                if v
            }
        )


class DeployCredentials(ActionModel, CredentialsModel):
    cdf_project: NonEmptyString
    cdf_cluster: NonEmptyString
    client_id: NonEmptyString = Field(alias="deployment_client_id")
    tenant_id: NonEmptyString = Field(alias="deployment_tenant_id")
    client_secret: NonEmptyString = Field(alias="deployment_client_secret")


class ConfigurationFile(ActionModel):
    config_file_path: NonEmptyString
    run_debug_mode: bool = False

    @validator("run_debug_mode", pre=True, always=True)
    def string_to_bool(cls, value):
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            elif value.lower() == "false":
                return False
        return value


class ExtPipeContact(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    send_notification: Optional[bool] = Field(
        default=False, alias="sendNotification"
    )  # TODO: Can this be none

    @classmethod
    def to_dict(cls, obj: "ExtPipeContact"):
        return {
            "name": obj.name,
            "email": obj.email,
            "role": obj.role,
            "sendNotification": obj.send_notification,
        }


class ExtPipeConfig(BaseModel):
    name: str
    external_id: str = Field(alias="externalId")
    description: Optional[str] = None
    metadata: Optional[dict[str, str]] = None
    contacts: Optional[list[ExtPipeContact]] = None
    data_set_id: int = Field(alias="dataSetId")  # TODO: can this be included?
    created_by: Optional[str] = Field(default=None, alias="createdBy")
    schedule: Optional[str] = None
    raw_tables: Optional[list[dict[str, str]]] = Field(
        default=None, alias="rawTables"
    )  # TODO: Might need to be a own class
    documentation: Optional[str] = None
    configuration: Optional[str] = None

    @validator("schedule")
    def validate_cron(cls, value):
        valid_values = ["On trigger", "Continuous", None]
        if value in valid_values:
            return value
        elif CronSlices.is_valid(value):
            return value
        else:
            raise ValueError(
                f"Received an invalid schedule: '{value}'. Notice that the values are case sensitive"
            )

    @validator("raw_tables")
    def validate_raw_tables(cls, raw_tables):
        if raw_tables is None:
            return raw_tables
        for raw_table in raw_tables:
            if list(raw_table.keys()) != ["dbName", "tableName"]:
                raise ValueError(
                    f"Wrong keys for raw_table '{raw_table}'. Each element in raw_tables must be on format '{{dbName:<insert-db-name>,tableName:<insert-table-name>}}'"
                )
        return raw_tables

    def to_extraction_pipeline(self) -> ExtractionPipeline:
        return ExtractionPipeline(
            name=self.name,
            external_id=self.external_id,
            description=self.description,
            metadata=self.metadata,
            data_set_id=self.data_set_id,
            contacts=self.contacts,
            source=self.source,
            documentation=self.documentation,
            created_by=self.created_by,
        )

    def to_extraction_pipeline_config(self) -> ExtractionPipelineConfig:
        # TODO: include description and potentially revision
        return ExtractionPipelineConfig(
            external_id=self.external_id, config=self.configuration
        )


class ExtPipesConfig(BaseModel):
    pipelines: list[ExtPipeConfig]


class RunConfig(BaseModel):
    deploy_creds: DeployCredentials
    extraction_pipelines: ExtPipesConfig


# Attributes that can be updated in an Extraction Pipeline Object
ExtPipesUpdateAttributes = {
    "contacts": ExtPipeContact.to_dict,
    "data_set_id": None,
    "description": None,
    "documentation": None,
    "metadata": None,
    "name": None,
    "raw_tables": None,
    "schedule": None,
    "source": None,
}
