inso-extpipes-cli
===
# Table Of Contents
- [inso-extpipes-cli](#inso-extpipes-cli)
- [Table Of Contents](#table-of-contents)
- [scope of work](#scope-of-work)
  - [to be done](#to-be-done)
- [how to run](#how-to-run)
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
1.1. Fill out/change `extpipes` from `example-config-extpipes.yml`
2. Change `.env_example` to `.env`
3. Fill out `.env`
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
        uses: cognitedata/inso-expipes-cli@main
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
