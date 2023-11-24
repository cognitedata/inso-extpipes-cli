import logging

from cognite.client.data_classes import (
    ExtractionPipeline,
    ExtractionPipelineContact,
    ExtractionPipelineList,
)
from jinja2 import Template

from .base import CommandBase


def _render_template(template: str, metadata: dict[str, str]) -> str:
    # Create a new Jinja2 template from the given template string
    jinja_template = Template(template)

    # Render the template using the provided metadata
    rendered_string = jinja_template.render(metadata)
    return rendered_string


class CommandDeploy(CommandBase):
    def command(self) -> None:
        # get existing extpipes
        existing_extpipes = self.client.extraction_pipelines.list(limit=-1)

        logging.debug(f"{existing_extpipes.as_external_ids()=}")

        # get requested from config
        requested_extpipes = ExtractionPipelineList(
            [
                ExtractionPipeline(  # key  # value
                    external_id=pipeline.external_id
                    if pipeline.external_id
                    else _render_template(self.naming_pattern, pipeline.metadata),
                    name=pipeline.name if pipeline.name else _render_template(self.naming_pattern, pipeline.metadata),
                    description=pipeline.description,
                    data_set_id=self.data_sets_in_scope.get(pipeline.data_set_external_id).id,  # type: ignore
                    raw_tables=[{"dbName": _t.db_name, "tableName": _t.table_name} for _t in pipeline.raw_tables],
                    schedule=pipeline.schedule,
                    contacts=[
                        ExtractionPipelineContact(
                            name=_c.name, email=_c.email, role=_c.role, send_notification=_c.send_notification
                        )
                        for _c in [*pipeline.contacts, *self.default_contacts]
                    ],
                    metadata=pipeline.metadata,
                    created_by=pipeline.created_by,
                )
                for pipeline in self.extpipes_config.pipelines
            ]
        )

        logging.debug(f"{requested_extpipes.as_external_ids()=}")

        # Cognite SDK v6.30.1 does NOT support UPSERT (with ExtractionPipelines)
        # build 3 lists create/update/delete
        create_extpipes = ExtractionPipelineList(
            [
                extpipe
                for extpipe in requested_extpipes
                if extpipe.external_id not in existing_extpipes.as_external_ids()
            ]
        )

        update_extpipes = ExtractionPipelineList(
            [extpipe for extpipe in requested_extpipes if extpipe.external_id in existing_extpipes.as_external_ids()]
        )

        delete_extpipes = [
            external_id
            for external_id in existing_extpipes.as_external_ids()
            if external_id not in requested_extpipes.as_external_ids()
        ]

        if create_extpipes:
            logging.info(f"Extraction pipelines to create:  {create_extpipes.as_external_ids()}")
        if update_extpipes:
            logging.info(f"Extraction pipelines to update:  {update_extpipes.as_external_ids()}")
        if self.extpipes_config.features.automatic_delete and delete_extpipes:
            logging.info(f"Extraction pipelines to delete:  {delete_extpipes}")

        if self.dry_run:
            logging.warning("Dry run detected. No changes to be applied to CDF.")
            return

        logging.info("Applying configuration")

        self.ensure_raw_tables()

        if self.extpipes_config.features.automatic_delete and delete_extpipes:
            self.client.extraction_pipelines.delete(external_id=delete_extpipes)
            logging.info(f"Extraction Pipelines deleted: {len(delete_extpipes)}")

        if create_extpipes:
            res = self.client.extraction_pipelines.create(create_extpipes)
            logging.info(f"Extraction Pipelines created: {len(res)}")

        if update_extpipes:
            res = self.client.extraction_pipelines.update(update_extpipes)
            logging.info(f"Extraction Pipelines updated: {len(res)}")
