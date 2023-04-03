# changelog
# * 220202 pa: copied first version from incubator-dataops notebook
# # *220404 tu: addition to versions on init, added semantic release instead
# * 220217 pa: v2 with a config-schema rewrite
#     * all names are now values, which cannot be changed by 'load_yaml(..)' util
#     * not specifc to bootstrap-cli name-convention anymore
#     * support of 'default-contacts' list

# tobedone:
# - [x] logger.info() or print() or click.echo(click.style(..))
#     - [ ] logger debug support
# - [x] make it clear what is not found (dataset in this case)
#     cognite.client.exceptions.CogniteNotFoundError: Not found: ['src:006:gdm']

# # dataops: external pipeline (`extpipes`) creation / deletion
# * this configuration driven approach builds on top of the "dataops:cdf-groups" approach

# * This approach uses stable Python SDK `client.extraction_pipeline`
#     * [SDK documentation](https://cognite-docs.readthedocs-hosted.com/projects/cognite-sdk-python/en/latest/cognite.html?highlight=experimental#extraction-pipelines} # noqa
#     * [API documentation](https://docs.cognite.com/api/v1/#tag/Extraction-Pipelines)

# ## to be done
# - [ ] cleanup of `imports`
# - [ ] cleanup of unused code(?)
# - [ ] validation of `schedule` values

# ## dependencies are validated
# * `schedule` only supports: `On trigger | Continuous | <cron expression> | null`

from typing import Dict, Optional

import click
from click import Context

from . import __version__
from .app_config import CommandMode
from .app_exceptions import ExtpipesConfigError
from .commands.deploy import CommandDeploy



# '''
#           888 d8b          888
#           888 Y8P          888
#           888              888
#   .d8888b 888 888  .d8888b 888  888
#  d88P"    888 888 d88P"    888 .88P
#  888      888 888 888      888888K
#  Y88b.    888 888 Y88b.    888 "88b
#   "Y8888P 888 888  "Y8888P 888  888
# '''


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(prog_name="extpipes_cli", version=__version__)
@click.option(
    "--cdf-project-name",
    help="CDF Project to interact with the CDF API, the 'PROJECT',"
    "environment variable can be used instead. Required for OAuth2 and optional for api-keys.",
    envvar="PROJECT",
)
# TODO: is cluster and alternative for host?
@click.option(
    "--cluster",
    default="westeurope-1",
    help="The CDF cluster where CDF Project is hosted (e.g. greenfield, europe-west1-1),"
    "Provide this or make sure to set the 'CLUSTER' environment variable. "
    "Default: westeurope-1",
    envvar="CLUSTER",
)
@click.option(
    "--host",
    default="https://westeurope-1.cognitedata.com/",
    help="The CDF host where CDF Project is hosted (e.g. https://westeurope-1.cognitedata.com),"
    "Provide this or make sure to set the 'HOST' environment variable."
    "Default: https://westeurope-1.cognitedata.com/",
    envvar="HOST",
)
# TODO: can we deprecate API_KEY option?
@click.option(
    "--api-key",
    help="API key to interact with the CDF API. Provide this or make sure to set the 'API_KEY',"
    "environment variable if you want to authenticate with API keys.",
    envvar="API_KEY",
)
@click.option(
    "--client-id",
    help="IdP client ID to interact with the CDF API. Provide this or make sure to set the "
    "'CLIENT_ID' environment variable if you want to authenticate with OAuth2.",
    envvar="CLIENT_ID",
)
@click.option(
    "--client-secret",
    help="IdP client secret to interact with the CDF API. Provide this or make sure to set the "
    "'CLIENT_SECRET' environment variable if you want to authenticate with OAuth2.",
    envvar="CLIENT_SECRET",
)
@click.option(
    "--token-url",
    help="IdP token URL to interact with the CDF API. Provide this or make sure to set the "
    "'TOKEN_URL' environment variable if you want to authenticate with OAuth2.",
    envvar="TOKEN_URL",
)
@click.option(
    "--scopes",
    help="IdP scopes to interact with the CDF API, relevant for OAuth2 authentication method. "
    "The 'SCOPES' environment variable can be used instead.",
    envvar="SCOPES",
)
@click.option(
    "--audience",
    help="IdP Audience to interact with the CDF API, relevant for OAuth2 authentication method. "
    "The 'AUDIENCE' environment variable can be used instead.",
    envvar="AUDIENCE",
)
@click.option(
    "--dotenv-path",
    help="Provide a relative or absolute path to an .env file (for command line usage only)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Print debug information",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Log only planned CDF API actions while doing nothing. Defaults to False.",
)
@click.pass_context
def extpipes_cli(
    # click.core.Context
    context: Context,
    # cdf
    cluster: str = "westeurope-1",
    cdf_project_name: Optional[str] = None,
    host: str = None,
    api_key: Optional[str] = None,
    # cdf idp
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    token_url: Optional[str] = None,
    scopes: Optional[str] = None,
    audience: Optional[str] = None,
    # cli
    # TODO: dotenv_path: Optional[click.Path] = None,
    dotenv_path: Optional[str] = None,
    debug: bool = False,
    dry_run: bool = False,
) -> None:
    context.obj = {
        # cdf
        "cluster": cluster,
        "cdf_project_name": cdf_project_name,
        "host": host,
        "api_key": api_key,
        # cdf idp
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": scopes,
        "token_url": token_url,
        "audience": audience,
        # cli
        "dotenv_path": dotenv_path,
        "debug": debug,
        "dry_run": dry_run,
    }


@click.command(help="Deploy a list of Extraction Pipelines from a configuration file")
@click.argument(
    "config-file",
    default="./config-extpipes.yml",
)
@click.option(
    "--automatic-delete",
    is_flag=True,
    help="Purge extpipes which are not specified in config-file (The default behavior is to keep the deployment in sync with the configuration)",
)
@click.pass_obj
def deploy(obj: Dict, config_file: str, automatic_delete: bool = True) -> None:
    click.echo(click.style("Deploying Extraction Pipelines...", fg="green"))

    try:
        command = CommandDeploy(config_file, command=CommandMode.DEPLOY, debug=obj["debug"], automatic_delete=automatic_delete, dry_run=obj["dry_run"])
        command.validate_config()
        command.command()

        click.echo(click.style("Extraction Pipelines deployed", fg="green"))

    except ExtpipesConfigError as e:
        exit(click.echo(click.style(e.message, fg="red")))


extpipes_cli.add_command(deploy)

def main() -> None:
    extpipes_cli()


if __name__ == "__main__":
    main()
