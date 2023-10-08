import logging
from typing import Dict

from cognite.client.data_classes import ExtractionPipeline, ExtractionPipelineContact
from jinja2 import Template

from .base import CommandBase


def _render_template(template: str, metadata: Dict[str, str]) -> str:
    # Create a new Jinja2 template from the given template string
    jinja_template = Template(template)

    # Render the template using the provided metadata
    rendered_string = jinja_template.render(metadata)
    return rendered_string


class CommandDeploy(CommandBase):
    def command(self) -> None:
        # get existing extpipes
        existing_extpipes = {ep.external_id: ep for ep in self.client.extraction_pipelines.list(limit=None)}

        # get requested from config
        requested_extpipes = {
            pipeline.external_id: ExtractionPipeline(  # key  # value
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
                created_by=self.client._config.client_name,
            )
            for pipeline in self.extpipes_config.pipelines
        }
        # Cognite SDK v6.30.1 does not support UPSERT (with ExtractionPipelineApply)
        # build 3 lists create/update/update
        create_extpipes = [
            extpipe
            for external_id, extpipe in requested_extpipes.items()
            if external_id not in existing_extpipes.keys()
        ]
        update_extpipes = [
            extpipe for external_id, extpipe in requested_extpipes.items() if external_id in existing_extpipes.keys()
        ]
        delete_extpipes = [
            external_id for external_id in existing_extpipes.keys() if external_id not in requested_extpipes.keys()
        ]

        if create_extpipes:
            logging.info(f"## Extraction pipelines to create:  {[extpipe.external_id for extpipe in create_extpipes]}")
        if update_extpipes:
            logging.info(f"## Extraction pipelines to update:  {[extpipe.external_id for extpipe in update_extpipes]}")
        if self.extpipes_config.features.automatic_delete and delete_extpipes:
            logging.info(f"## Extraction pipelines to delete:  {[extpipe.external_id for extpipe in update_extpipes]}")

        if self.dry_run:
            logging.warning("Dry run detected. No changes to be applied to CDF.")
            return

        logging.info("## Applying configuration")

        self.ensure_raw_tables()

        if self.extpipes_config.features.automatic_delete and delete_extpipes:
            logging.info(f"## Extraction pipelines to delete:  {delete_extpipes}")
            self.client.extraction_pipelines.delete(external_id=delete_extpipes)

        if create_extpipes:
            res = self.client.extraction_pipelines.create(create_extpipes)
            logging.info(f"Extraction Pipelines created: {len(res)}")

        if update_extpipes:
            res = self.client.extraction_pipelines.update(update_extpipes)
            logging.info(f"Extraction Pipelines updated: {len(res)}")
