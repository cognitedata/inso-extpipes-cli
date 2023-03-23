import logging
from datetime import datetime
from typing import Dict, List, TypeVar

from cognite.client.data_classes import ExtractionPipeline, ExtractionPipelineContact, ExtractionPipelineList

from .. import __version__
from ..app_config import YesNoType
from .base import CommandBase

# type hints
External_ids = List[str]


class CommandDeploy(CommandBase):

    # '''
    #        .o8                       oooo
    #       "888                       `888
    #   .oooo888   .ooooo.  oo.ooooo.   888   .ooooo.  oooo    ooo
    #  d88' `888  d88' `88b  888' `88b  888  d88' `88b  `88.  .8'
    #  888   888  888ooo888  888   888  888  888   888   `88..8'
    #  888   888  888    .o  888   888  888  888   888    `888'
    #  `Y8bod88P" `Y8bod8P'  888bod8P' o888o `Y8bod8P'     .8'
    #                        888                       .o..P'
    #                       o888o                      `Y8P'
    # '''
    def command(self, automatic_delete: YesNoType) -> None:

        # check click parameter and map from YesNoType to bool
        # if provided they override configuration or defaults from yaml-config
        if automatic_delete:
            self.automatic_delete = automatic_delete == YesNoType.yes

        # debug new features and override with cli-parameters
        logging.debug(f"From cli: {automatic_delete=}")

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
        logging.info("## extraction pipelines to create:")
        logging.info(new_ids)

        delete_ids: External_ids = []
        if self.automatic_delete:
            # delete non specified (configured) extpipes, to keep the deployment in sync
            delete_ids = get_delete_ids(requested_dict.keys(), existing_extpipes_dict.keys())
            logging.info("## extraction pipelines to delete:")
            logging.info(delete_ids)

            if self.is_dry_run:
                logging.info(f"Dry run - Extraction Piplines deleting with extIds: {delete_ids=}")
            else:
                self.client.extraction_pipelines.delete(external_id=delete_ids)

        else:
            logging.info("## skipping automatic-delete: configuration deactivated")

        # updated = self.client.extraction_pipelines.update(
        #   [ep for ep in transformations if ep.external_id in existing_ids]
        # )
        # created: ExtractionPipelineList = self.client.extraction_pipelines.create(
        #     [ep for external_id, ep in requested_dict.items() if external_id in new_ids]
        # )
        # xxx pa: switch to create extpipes one by one to bypass an issue
        if self.is_dry_run:
            logging.info(
                "Dry run - Extraction Pipelines creating with extIds: "
                f"{[external_id for external_id, _ in requested_dict.items() if external_id in new_ids]}"
            )
        else:
            created: ExtractionPipelineList = [
                self.client.extraction_pipelines.create(ep)
                for external_id, ep in requested_dict.items()
                if external_id in new_ids
            ]
            logging.info(f"Extraction Pipelines: created: {len(created)}, deleted: {len(delete_ids)}")

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
            external_id = (
                f"{kwargs['pipeline'].source+':' if kwargs['pipeline'].source else ''}"
                f"{kwargs['rawdb'].short_name or kwargs['rawdb'].rawdb_name}:"
                f"{kwargs['rawtable'].short_name or kwargs['rawtable'].rawtable_name}"
                f"{':'+kwargs['pipeline'].suffix if kwargs['pipeline'].suffix else ''}"
            )
            assert len(external_id) < 140, f"name= {external_id} is too long (max 140 characters)"
            # assert len(external_id) < 255, f'external_id= {external_id} is too long'
            # logging.info(external_id)
            return external_id

            # return f"{kwargs['pipeline']}:{':'.join(kwargs['group'].split(':')[:2])}:{kwargs['tableName']}"

        def description_template(**kwargs):
            # pipeline: adf
            # tableName: un_ports
            # output:
            # UN_PORTS integration through ADF
            description = (
                f"{kwargs['rawtable'].rawtable_name.upper()} "
                f"{'integration through ' + kwargs['pipeline'].source.upper() if kwargs['pipeline'].source else ''}"
            )
            assert len(description) < 500, f"name= {description} is too long (max 500 characters)"
            # logging.info(description)
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
                    ExtractionPipelineContact(**contact.dict())
                    for contact in (pipeline.contacts or self.default_contacts)
                ],
                # no validation yet
                schedule=pipeline.schedule,
            )
            for rawdb in self.extpipes_config.rawdbs
            for rawtable in rawdb.rawtables
            for pipeline in rawtable.pipelines
        }
