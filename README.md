inso-extpipes-cli
===
# Table Of Contents
- [inso-extpipes-cli](#inso-extpipes-cli)
- [Table Of Contents](#table-of-contents)
- [scope of work](#scope-of-work)
  - [to be done](#to-be-done)
- [how to run](#how-to-run)
  - [Configuration](#configuration)
    - [Configuration for all commands](#configuration-for-all-commands)
    - [Configuration for `deploy` command](#configuration-for-deploy-command)
  - [run local with poetry](#run-local-with-poetry)
  - [run local with Python](#run-local-with-python)
  - [run local with Docker](#run-local-with-docker)
  - [run as github action](#run-as-github-action)
- [Contribute](#contribute)
      - [Versioning](#versioning)
# scope of work

- the prefix `inso-` names this solution as provided by Cognite Industry Solution team, and is not (yet) an offical supported cli / GitHub Action  from Cognite
  - it provides a configuration driven deployment for Cognite Extraction Pipelines (named `extpipes` in short)
  - support to run it
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
- [ ] logger.info() or print() or click.echo(click.style(..))
    - logger debug support
- [ ] compile as EXE (when Python is not available on customer server)
  - code-signed exe required for Windows

# how to run
Follow the initial setup first

1. Fill out relevant configurations from `configs`
   - Fill out/change `extpipes` from `example-config-extpipesv2.yml`
2. Change `.env_example` to `.env`
3. Fill out `.env`

## Configuration

A YAML configuration file must be passed as an argument when running the program.
Different configuration file used for delete and prepare/deploy

### Configuration for all commands

All commands share a `cognite` and a `logger` section in the YAML manifest, which is common to our Cognite Database-Extractor configuration.

The configuration file supports variable-expansion (`${BOOTSTRAP_**}`), which are provided either as
1. environment-variables,
2. through an `.env` file or
3. command-line parameters

Here is an example:

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


logger:
  file:
    path: ./logs/test-deploy.log
    level: INFO
  console:
    level: INFO
```
### Configuration for `deploy` command

In addition to the sections described above, the configuration file for `deploy` command requires three more sections, which will be loaded by Python

```python
@dataclass
class ExtpipesConfig
  ...
```

- `extpipe-pattern` - format-string of the extpipes names (and externalIds), at them moment only for documentation
- `default-contacts` - list of contacts which will be added to extpipes as default, if not explict configured on pipeline level
  - defined through list of
    - `name`
    - `email`
    - `role`: `str`
    - `send-notification` : `true|false`
- `rawdbs`
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
        uses: cognitedata/inso-extpipes-cli@main
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
