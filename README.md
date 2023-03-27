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
  - [run local with Python](#run-local-with-python)
  - [run local with Docker](#run-local-with-docker)
  - [run as github action](#run-as-github-action)
- [Contribute](#contribute)
      - [Versioning](#versioning)
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
  host: ${EXTPIPES_CDF_HOST}
  project: ${EXTPIPES_CDF_PROJECT}
  #
  # AAD IdP login credentials:
  #
  idp-authentication:
    client-id: ${EXTPIPES_IDP_CLIENT_ID}
    secret: ${EXTPIPES_IDP_CLIENT_SECRET}
    scopes:
      - ${EXTPIPES_IDP_SCOPES}
    token_url: ${EXTPIPES_IDP_TOKEN_URL}

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

- `EXTPIPES_CDF_HOST`
  - The URL to your CDF cluster.
  - Example: `https://westeurope-1.cognitedata.com`
- `EXTPIPES_CDF_PROJECT`
  - The CDF project.
- `EXTPIPES_IDP_CLIENT_ID`
  - The client ID of the app registration you have created for the CLI.
- `EXTPIPES_IDP_CLIENT_SECRET`
  - The client secret you have created for the app registration,
- `EXTPIPES_IDP_TOKEN_URL = https://login.microsoftonline.com/<tenant id>/oauth2/v2.0/token`
  - If you're using Azure AD, replace `<tenant id>` with your Azure tenant ID.
- `EXTPIPES_IDP_SCOPES`
  - Usually: `https://<cluster-name>.cognitedata.com/.default`

### Configuration for `deploy` command

In addition to the sections described above, the configuration file for `deploy` command requires more sections (some of them optional):


- `extpipe-pattern` - optional format-string of the extpipes names (and externalIds), at them moment only for documentation and not used from implementation
- `default-contacts` - optional list of contacts which will be added to extpipes as default, if not explict configured on pipeline level
  - defined through list of
    - `name`
    - `email`
    - `role`: `str`
    - `send-notification` : `true|false`
- `automatic-delete` - `true|false` optional flag, defaults to `true`
- `rawdbs` (**your main configuration goes here**)
  - defined through list of
    - `rawdb-name`
    - `dataset-external-id`
    - `short-name`
    - `rawtables`
      - defined through list of
        - `rawtable-name`
        - `pipelines`
          - defined through list of
            - `source`
            - `schedule` : `Continuous|On trigger`
            - `skip-rawtable` : `true|false` (default `false`)
            - `suffix`
            - `contacts`
              - defined through list of
                - `name`
                - `email`
                - `role`: `str`
                - `send-notification` : `true|false`

Configuration example:

```yaml
# extpipe-pattern only documentation atm
extpipe-pattern: '{source}:{short-name}:{rawtable-name}:{suffix}'

# new since v2.1.0
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

# following configuration creates four extpipes with names:
#   adf:src:001:sap_funcloc
#   db:src:001:sap_equipment
#   az-func:src:002:weather_europe:hourly
#   az-func:src:002:weather_europe:daily
rawdbs:
  # list of raw-dbs > containing rawtables > containing pipelines
  - rawdb-name: src:001:sap:rawdb
    dataset-external-id: src:001:sap
    short-name: src:001
    rawtables:
      - rawtable-name: sap_funcloc
        pipelines:
        # source is a short-name identifying the pipeline source being
        # a 'db-extractor (db)', an 'Azure Function (az-func)',
        # or 'Azure Data Factory (adf)', 'Python script (py)', ..
        - source: adf
          schedule: Continuous
          # since v2.2.0 'skip-rawtable' with default 'false' exists
          # It allows to skip creation of the rawtable,
          # to avoid automatic creation in case it is not needed
          # FYI: Next v3 release will change the config-schema, to express
          # raw-tables not being a leading, but optional element
          skip-rawtable: false
      - rawtable-name: sap_equipment
        pipelines:
        - source: db
          schedule: Continuous
          # default-contacts can be overwritten
          contacts:
            - name: Fizz Buzz
              email: fizzbuzz@cognite.com
              role: admin
              send-notification: true
  - rawdb-name: src:002:weather:rawdb
    dataset-external-id: src:002:weather
    short-name: src:002
    rawtables:
      - rawtable-name: weather_europe
        # multiple pipelines for same raw-table
        pipelines:
        - source: az-func
          suffix: hourly
          schedule: Continuous
        - source: az-func
          suffix: daily
          schedule: Continuous
```
## run local with poetry

```bash
poetry build
poetry install
poetry update

poetry run extpipes-cli deploy --debug configs/example-config-extpipes.yml
```

## run local with Python

```bash
export PYTHONPATH=.

python incubator/extpipes_cli/__main__.py deploy configs/example-config-extpipes.yml
```

## run local with Docker
- `.dockerignore` file
- volumes for `configs` (to read) and `logs` folder (to write)

```bash
docker build -t incubator/extpipes:v1.0 -t incubator/extpipes:latest .

# ${PWD} because only absolute paths can be mounted
docker run -it --volume ${PWD}/configs:/configs --volume ${PWD}/logs:/logs  --env-file=.env incubator/extpipes deploy /configs/example-config-extpipes.yml
```

Try to debug container
- requires override of `ENTRYPOINT`
  - `/bin/bash` not available but `sh`
- no `ls` available :/

```bash
docker run -it --volume ${PWD}/configs:/configs --env-file=.env --entrypoint /bin/sh incubator/extpipes
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
      CDF_PROJECT: yourcdfproject
      CDF_CLUSTER: bluefield
      IDP_TENANT: abcde-12345
      CDF_HOST: https://bluefield.cognitedata.com/
      - name: Deploy extpipes
        # best practice is to use a tagged release (and not '@main')
        # find a released tag here: https://github.com/cognitedata/inso-extpipes-cli/releases
        uses: cognitedata/inso-expipes-cli@v2.1.0
        env:
            EXTPIPES_IDP_CLIENT_ID: ${{ secrets.CLIENT_ID }}
            EXTPIPES_IDP_CLIENT_SECRET: ${{ secrets.CLIENT_SECRET }}
            EXTPIPES_CDF_HOST: ${{ env.CDF_HOST }}
            EXTPIPES_CDF_PROJECT: ${{ env.CDF_PROJECT }}
            EXTPIPES_IDP_TOKEN_URL: https://login.microsoftonline.com/${{ env.IDP_TENANT }}/oauth2/v2.0/token
            EXTPIPES_IDP_SCOPES: ${{ env.CDF_HOST }}.default
        # additional parameters for running the action
        with:
          config_file: ./configs/example-config-extpipes.yml
```
# Contribute
1. `poetry install`
2. To run all checks locally - which is typically needed if the GitHub check is failing - e.g. you haven't set up `pre-commit` to run automatically:
  -  `poetry run pre-commit install`  # Only needed if not installed
  -  `poetry run pre-commit run --all-files`
#### Versioning
- Uses `semantic-release` to create version tags.
- The rules for commit messages are conventional commits, see [conventionalcommits](https://www.conventionalcommits.org/en/v1.0.0-beta.4/#summary%3E)
- Remark: If version needs change, before merge, make sure commit title has elements mentioned on `conventionalcommits`
- Remark: with new version change, bump will update the version on `pyproject.toml` so no need to change version there.
- Remark: version in `incubator/extpipes_cli/__init__` is used in main to add version on metadata.
  This is not a part of semantic release but needs to be updated to upcoming version before version update.
