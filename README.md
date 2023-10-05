inso-extpipes-cli
===
# Table Of Contents
- [inso-extpipes-cli](#inso-extpipes-cli)
- [Table Of Contents](#table-of-contents)
- [scope of work](#scope-of-work)
  - [to be done](#to-be-done)
- [how to run](#how-to-run)
- [ExtPipes CLI commands](#extpipes-cli-commands)
  - [`Deploy` command](#deploy-command)
  - [Configuration](#configuration)
    - [Configuration for all commands](#configuration-for-all-commands)
      - [Environment variables](#environment-variables)
    - [Configuration for `deploy` command](#configuration-for-deploy-command)
  - [run local with poetry](#run-local-with-poetry)
  - [run local with Python and Poetry](#run-local-with-python-and-poetry)
  - [Run locally with Docker](#run-locally-with-docker)
    - [production build](#production-build)
    - [development build](#development-build)
  - [run as github action](#run-as-github-action)
- [Contribute](#contribute)
  - [Semantic Versioning](#semantic-versioning)
# scope of work

- It provides a configuration driven deployment for Cognite Extraction Pipelines (named `extpipes` in short)
- Support to run it
    - from `poetry run`
    - from `python -m`
    - from `docker run`
    - and as GitHub Action

- templates used for implementation are
  - `cognitedata/transformation-cli`
  - `cognitedata/python-extratcion-utils`
    - using `CogniteConfig` and `LoggingConfig`
    - and extended with custom config sections
  - the configuration structure and example expects a CDF Project configured with `cognitedata/inso-cdf-project-cli`

## to be done

- [x] `.dockerignore` (pycache)
- [x] logs folder handling (docker volume mount)
- [x] logger.info() or print() or click.echo(click.style(..))
    - logger debug support
- [ ] compile as EXE (when Python is not available on customer server)
  - code-signed exe required for Windows

# how to run
Follow the initial setup first

1. Fill out relevant configurations from `configs`
   - Fill out/change `extpipes` from `example-config-extpipesv2.yml`
2. Change `.env_example` to `.env`
3. Fill out `.env`

# ExtPipes CLI commands

## `Deploy` command

The extpipes-cli `deploy` command applies the configuration file settings to your CDF project and creates the necessary CDF Extraction-Pipelines.

By default it is **automatically deleting** CDF Extraction-Pipelines which are not
covered by the given configuration. You can deactivate this with the
- `--automatic-delete no` parameter
- or the `automatic-delete: false` in configuration-file.

The command also is the configured to run used from a GitHub-Action workflow.

```bash
➟  extpipes-cli --help
Usage: extpipes-cli [OPTIONS] COMMAND [ARGS]...

Options:
  --version                Show the version and exit.
  --dry-run [yes|no]       Log only planned CDF API actions while doing
                           nothing. Defaults to 'no'.
```

```bash
➟  extpipes-cli deploy --help
Usage: extpipes-cli deploy [OPTIONS] [CONFIG_FILE]

  Deploy a set of extpipes from a config-file

Options:
  --debug                      Print debug information
  --automatic-delete [yes|no]  Purge extpipes which are not specified in
                               config-file automatically (this is the default
                               behavior, to keep deployment in sync with
                               configuration)
  -h, --help                   Show this message and exit.
```

## Configuration

You must pass a YAML configuration file as an argument when running the program.

### Configuration for all commands

_(January'23: only one command is supported right now, but the CLI solution can be extended in the future)_

All commands share a `cognite` and a `logger` section in the YAML manifest, which is common to our Cognite Database-Extractor configuration.

The configuration file supports variable-expansion (`${EXTPIPES_**}`), which are provided either
1. As environment-variables,
2. Through an `.env` file (Note: this doesn't overwrite existing environment variables.)
3. As command-line parameters

Below is an example configuration:

```yaml
# follows the same parameter structure as the DB extractor configuration
cognite:
  host: ${HOST}
  project: ${PROJECT}
  #
  # AAD IdP login credentials:
  #
  idp-authentication:
    client-id: ${CLIENT_ID}
    secret: ${CLIENT_SECRET}
    scopes:
      - ${SCOPES}
    token_url: ${TOKEN_URL}

# https://docs.python.org/3/library/logging.config.html#logging-config-dictschema
logging:
  version: 1
  formatters:
    formatter:
      # class: "tools.formatter.StackdriverJsonFormatter"
      format: "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
  handlers:
    file:
      class: "logging.FileHandler"
      filename: ./logs/deploy-trading.log
      formatter: "formatter"
      mode: "w"
      level: "DEBUG"
    console:
      class: "logging.StreamHandler"
      level: "DEBUG"
      formatter: "formatter"
      stream: "ext://sys.stderr"
  root:
    level: "DEBUG"
    handlers: [ "console", "file" ]
```

#### Environment variables

Details about the environment variables:

- `HOST`
  - The URL to your CDF cluster.
  - Example: `https://westeurope-1.cognitedata.com`
- `PROJECT`
  - The CDF project.
- `CLIENT_ID`
  - The client ID of the app registration you have created for the CLI.
- `CLIENT_SECRET`
  - The client secret you have created for the app registration,
- `TOKEN_URL = https://login.microsoftonline.com/<tenant id>/oauth2/v2.0/token`
  - If you're using Azure AD, replace `<tenant id>` with your Azure tenant ID.
- `SCOPES`
  - Usually: `https://<cluster-name>.cognitedata.com/.default`

### Configuration for `deploy` command

In addition to the sections described above, the configuration file for `deploy` command requires more sections (some of them optional):

Configuration example:

```yaml
extpipes:
  features:
    # NOT USED: extpipe-pattern only documentation atm
    extpipe-pattern: '{source}:{short-name}:{table-name}:{suffix}'

    # The default and recommended value is: true
    # to keep the deployment in sync with configuration
    # which means non configured extpipes get automatically deleted
    automatic-delete: true

    # can contain multiple contacts, can be overwritten on pipeline level
    default-contacts:
      - name: Yours Truly
        email: yours.truly@cognite.com
        role: admin
        send-notification: false

  pipelines:
      # required
      # max 255 char, external-id provided by client
    - external-id: src:001:sap:sap_funcloc:continuous
      # optional: str, default to external-id
      name: src:001:sap:sap_funcloc:continuous
      # optional: str
      description: describe or defaults to auto-generated description, that it is "deployed through extpipes-cli@v3.0.0"
      # optional: str
      data-set-external-id: src:001:sap
      # optional: "On trigger", "Continuous" or cron expression
      schedule: Continuous
      # optional: [{},{}]
      # defaults to features.default-contacts (if exist)
      contacts:
        - name: Fizz Buzz
          email: fizzbuzz@cognite.com
          role: admin
          send-notification: true
      # optional: str
      source: az-func
      # optional: {}
      metadata:
        version: extpipes-cli@v3.1.0
      # optional: str max 10000 char
      # Documentation text field, supports Markdown for text formatting.
      documentation: Documentation which can include Mermaid diagrams?
      # optional: str
      # Usually user email is expected here, defaults to extpipes + version?
      created-by: extpipes-cli@v3.1.0

      # optional: [{},{}]
      raw-tables:
        - db-name: src:001:sap
          table-name: sap_funcloc

      # optional: {}
      extpipe-config:
        # str
        config: |
          nested yaml/json/ini which is simply a string for this config
        # optional: str
        description: describe the config, or autogenerate?
```
## run local with poetry

```bash
poetry build
poetry install
poetry update

poetry run extpipes-cli deploy --debug configs/example-config-extpipes.yml
```

## run local with Python and Poetry

```bash
poetry shell
# extpipes-cli is defined in pyproject.toml
extpipes-cli deploy ./configs/example-config-extpipes.yml
```

## Run locally with Docker

### production build
- `.dockerignore` file
- volumes for `configs` (to read) and `logs` folder (to write)

```bash
docker build -t extpipes-cli:prod --target=production .

# ${PWD} because only absolute paths can be mounted
# poerty project is deplopyed to /opt/extpipes-cli/
docker run --env-file=.env --volume ${PWD}/configs:/configs --volume ${PWD}/logs:/opt/extpipes-cli/logs extpipes-cli:prod deploy /configs/config-deploy-example.yml
```

### development build

Debugging the Docker container with all dev-dependencies and poetry installed

- volumes for `configs` (to read) and `logs` folder (to write)
- volumes for `src` (to read/write)

```bash
# using the 'development' target of the Dockerfile multi-stages
➟  docker build -t extpipes-cli:dev --target=development .

# start bash in container
➟  docker run --env-file=.env --volume ${PWD}/configs:/configs --volume ${PWD}/logs:/logs --volume ${PWD}/src://opt/extpipes-cli/src -it --entrypoint /bin/bash extpipes-cli:dev

# run project from inside container
> poetry shell
> extpipes-cli --help
> extpipes-cli --dry-run yes deploy /configs/config-deploy-example.yml
# logs are available on your host in mounted '.logs/' folder
# 'src/' changes are mounted to your host ./src folder
```


## run as github action

```yaml
jobs:
  deploy:
    name: Deploy Extraction Pipelines
    environment: dev
    runs-on: ubuntu-latest
    # environment variables
    env:
      PROJECT: yourcdfproject
      CLUSTER: bluefield
      IDP_TENANT: abcde-12345
      HOST: https://bluefield.cognitedata.com/
      - name: Deploy extpipes
        # best practice is to use a tagged release (and not '@main')
        # find a released tag here: https://github.com/cognitedata/inso-extpipes-cli/releases
        uses: cognitedata/inso-expipes-cli@v2.2.1
        env:
            CLIENT_ID: ${{ secrets.CLIENT_ID }}
            CLIENT_SECRET: ${{ secrets.CLIENT_SECRET }}
            HOST: ${{ env.HOST }}
            PROJECT: ${{ env.PROJECT }}
            TOKEN_URL: https://login.microsoftonline.com/${{ env.IDP_TENANT }}/oauth2/v2.0/token
            SCOPES: ${{ env.HOST }}.default
        # additional parameters for running the action
        with:
          config_file: ./configs/example-config-extpipes.yml
```
# Contribute
1. `poetry install`
2. To run all checks locally - which is typically needed if the GitHub check is failing - e.g. you haven't set up `pre-commit` to run automatically:
  - `poetry install && poetry shell`
  - `pre-commit install`  # Only needed if not installed
  - `pre-commit run --all-files`

## Semantic Versioning
- Uses `semantic-release` to create version tags.
- The rules for commit messages are conventional commits, see [conventionalcommits](https://www.conventionalcommits.org/en/v1.0.0-beta.4/#summary%3E)
- Remark: If version needs change, before merge, make sure commit title has elements mentioned on `conventionalcommits`
- Remark: with new version change, bump will automatically update
  - the version on `pyproject.toml`
  - the version in `src/extpipes/__init__` (used by `--version` parameter).
