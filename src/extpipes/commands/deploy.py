import logging

from cognite.client.data_classes import ExtractionPipeline

from .. import __version__
from ..app_config import CommandMode
from .base import CommandBase


class CommandDeploy(CommandBase):
    def __init__(self, config_file, command: CommandMode = CommandMode.DEPLOY, debug: bool = False, automatic_delete: bool = True, dry_run: bool = False):
        super().__init__(config_file, command=command, debug=debug, dry_run=dry_run)
        self.automatic_delete = automatic_delete

    def command(self) -> None:
        # get existing extpipes
        existing_extpipes = {ep.external_id: ep for ep in self.client.extraction_pipelines.list(limit=None)}

        # get requested from config
        requested_extpipes = {
            pipeline.external_id:  # key
            ExtractionPipeline(  # value
                external_id=pipeline.external_id,
                name=pipeline.name,
                description=pipeline.description,
                data_set_id=self.client.data_sets.retrieve(external_id=pipeline.data_set_external_id).id,
                raw_tables=None,
                schedule=pipeline.schedule,
                contacts=pipeline.contacts,
                metadata=pipeline.metadata,
                created_by=self.client._config.client_name
            )
            for pipeline in self.extpipes_config.pipelines
        }

        # build 3 lists create/update/update
        create_extpipes = [extpipe for external_id, extpipe in requested_extpipes.items() if external_id not in existing_extpipes.keys()]
        update_extpipes = [extpipe for external_id, extpipe in requested_extpipes.items() if external_id in existing_extpipes.keys()]
        delete_extpipes = [external_id for external_id in existing_extpipes.keys() if external_id not in requested_extpipes.keys()]

        logging.info(f"## Extraction pipelines to create:  {[extpipe.external_id for extpipe in create_extpipes]}")
        logging.info(f"## Extraction pipelines to update:  {[extpipe.external_id for extpipe in update_extpipes]}")

        if delete_extpipes:
            if self.automatic_delete:
                logging.info(f"## Extraction pipelines to delete:  {delete_extpipes}")
            else:
                logging.info(f"## These extraction pipelines are in CDF but not configured:  {delete_extpipes}")

        if self.dry_run:
            logging.warning(f"Dry Run finished!")

        else:
            if create_extpipes:
                res = self.client.extraction_pipelines.create(create_extpipes)
                logging.info(f"Extraction Pipelines created: {len(res)}")

            if update_extpipes:
                res = self.client.extraction_pipelines.update(update_extpipes)
                logging.info(f"Extraction Pipelines updated: {len(res)}")

            if self.automatic_delete and delete_extpipes:
                # returns None if successful
                self.client.extraction_pipelines.delete(external_id=delete_extpipes)
                logging.info(f"Extraction Pipelines deleted: {len(delete_extpipes)}")
