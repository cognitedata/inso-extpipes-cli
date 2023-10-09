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
from pydantic import ValidationError

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
    help="CDF Project to interact with the CDF API, the 'CDF_PROJECT',"
    "environment variable can be used instead. Required for OAuth2.",
    envvar="CDF_PROJECT",
)
# TODO: is cluster and alternative for host?
@click.option(
    "--cluster",
    default="api",
    help="The CDF cluster where CDF Project is hosted (e.g. api, europe-west1-1),"
    "Provide this or make sure to set the 'CLCDF_USTER' environment variable. "
    "Default: api",
    envvar="CDF_CLUSTER",
)
@click.option(
    "--host",
    default="https://api.cognitedata.com/",
    help="The CDF host where CDF Project is hosted (e.g. https://api.cognitedata.com),"
    "Provide this or make sure to set the 'CDF_HOST' environment variable."
    "Default: https://api.cognitedata.com/",
    envvar="CDF_HOST",
)
@click.option(
    "--client-id",
    help="IdP client ID to interact with the CDF API. Provide this or make sure to set the "
    "'CDF_CLIENT_ID' environment variable if you want to authenticate with OAuth2.",
    envvar="CDF_CLIENT_ID",
)
@click.option(
    "--client-secret",
    help="IdP client secret to interact with the CDF API. Provide this or make sure to set the "
    "'CDF_CLIENT_SECRET' environment variable if you want to authenticate with OAuth2.",
    envvar="CDF_CLIENT_SECRET",
)
@click.option(
    "--token-url",
    help="IdP token URL to interact with the CDF API. Provide this or make sure to set the "
    "'CDF_TOKEN_URL' environment variable if you want to authenticate with OAuth2.",
    envvar="CDF_TOKEN_URL",
)
@click.option(
    "--scopes",
    help="IdP scopes to interact with the CDF API, relevant for OAuth2 authentication method. "
    "The 'CDF_SCOPES' environment variable can be used instead.",
    envvar="CDF_SCOPES",
)
@click.option(
    "--audience",
    help="IdP Audience to interact with the CDF API, relevant for OAuth2 authentication method. "
    "The 'CDF_AUDIENCE' environment variable can be used instead.",
    envvar="CDF_AUDIENCE",
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
    cluster: str = "api",
    cdf_project_name: Optional[str] = None,
    host: str = None,
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
    help="Delete extpipes which are not specified in config-file",
)
@click.pass_obj
def deploy(obj: Dict, config_file: str, automatic_delete: bool = True) -> None:
    click.echo(click.style("Deploying Extraction Pipelines...", fg="green"))

    try:
        command = CommandDeploy(
            config_file,
            command=CommandMode.DEPLOY,
            debug=obj["debug"],
            dry_run=obj["dry_run"],
            dotenv_path=obj["dotenv_path"],
        )
        command.validate_config()
        command.command()

        click.echo(click.style("Extraction Pipelines deployed", fg="green"))
    except ValidationError as e:
        for error in e.errors():
            field_path = ".".join(map(str, error["loc"]))  # Convert tuple path (including indices) to dot notation
            click.echo(f"Error in field '{field_path}': {error['msg']}")
        exit(code=126)
    except ExtpipesConfigError as e:
        click.echo(click.style(e.message, fg="red"))
        exit(code=127)


extpipes_cli.add_command(deploy)


def main() -> None:
    extpipes_cli()


if __name__ == "__main__":
    main()
