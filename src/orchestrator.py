import logging

from cognite.client import CogniteClient
from cognite.client.data_classes import ExtractionPipelineConfig, ExtractionPipelineUpdate

from configs import ExtPipesConfig, ExtPipesUpdateAttributes


def upsert_extraction_pipelines(client: CogniteClient, eps_config: ExtPipesConfig):
    existing_eps = set([ep.external_id for ep in client.extraction_pipelines.list(limit=None)])

    new_eps = [ep for ep in eps_config.pipelines if ep.external_id not in existing_eps]
    update_eps = [ep for ep in eps_config.pipelines if ep.external_id in existing_eps]

    if new_eps:
        logging.info(f"New extraction pipelines: {len(new_eps)}")
        for ep in new_eps:
            logging.debug(f"Create new extraction pipeline '{ep.external_id}'")
            # TODO: Consider solving this another way. Configuration is not a parameter, so it must be removed
            client.extraction_pipelines.create([ep.model_dump(by_alias=True, exclude="configuration")])
            upsert_extraction_pipeline_config(client=client, eps=[ep])
        logging.debug("Completed creating new extraction pipelines")

    if update_eps:
        logging.debug(f"Update extraction pipelines: {len(update_eps)}")
        logging.debug("Collecting updates from extraction pipelines")
        for ep in update_eps:
            ep_update = ExtractionPipelineUpdate(external_id=ep.external_id)
            for update_attr, attrib_func in ExtPipesUpdateAttributes.items():
                if (new_attr := getattr(ep, update_attr, False)) is not False:
                    # Used to covert attributes of certain data objects to a valid format
                    if attrib_func:
                        new_attr = [attrib_func(attr) for attr in new_attr]

                    attrib_method = getattr(ep_update, update_attr)
                    if attrib_method is None:
                        raise AttributeError(
                            f"Failed to find attribute '{update_attr}' in ExtractionPipelineUpdate. Please report error"
                        )

                    setter_method = getattr(attrib_method, "set")
                    if callable(setter_method):
                        setter_method(new_attr)
                    else:
                        raise AttributeError(
                            f"Failed to find setter method for ExtractionPipelineAttribute '{update_attr}'. Please report error"
                        )

            # Update one by one to make it easier for user to see if certain parts of the configuration is invalid
            logging.info(f"Updating extraction pipeline '{ep.external_id}'")
            client.extraction_pipelines.update(ep_update)
            upsert_extraction_pipeline_config(client=client, eps=[ep])

        logging.debug("Completed updating extraction pipelines")


def upsert_extraction_pipeline_config(client: CogniteClient, eps: list[ExtPipesConfig]):
    eps_with_config = [ep for ep in eps if ep.configuration]
    for ep in eps_with_config:
        client.extraction_pipelines.config.create(
            ExtractionPipelineConfig(external_id=ep.external_id, config=ep.configuration)
        )
