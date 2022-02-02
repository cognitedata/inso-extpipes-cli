# scope of work

- the prefix `inso-` names this solution as provided by Cognite Industry Solution team, and is nit (yet? :)) an offical supported cli from Cognite
- it provides a configuration driven deployment for Cognite Extraction Pipelines (named `extpipes` in short)
  - support to run it 
    - from `poetry run`
    - from `python -m`
    - from `docker run`
    - and as gh-action

- template used for implementation are
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
- [ ] change / config for `ExtractionPipelineContact` (atm Peter Arwanitis)

# how to run
## run local with poetry and .env

```bash
poetry build
poetry install
poetry update

poetry run extpipes-cli deploy --debug configs/test-dev-extpipes.yml
```

## run local with Python

```bash
export PYTHONPATH=.

python incubator/extpipes_cli/__main__.py deploy configs/test-dev-extpipes.yml 
```

## run local with Docker and .env
- `.dockerignore` file
- volumes for `configs` (to read) and `logs` folder (to write)

```bash
docker build -t incubator/extpipes:v1.0 -t incubator/extpipes:latest .

# ${PWD} because only absolute paths can be mounted
docker run -it --volume ${PWD}/configs:/configs --volume ${PWD}/logs:/logs  --env-file=.env incubator/extpipes deploy /configs/test-dev-extpipes.yml
```

Try to debug container
- requires override of `ENTRYPOINT`
  - `/bin/bash` not available but `sh`
- no `ls` available :/

```bash
docker run -it --volume ${PWD}/configs:/configs --env-file=.env --entrypoint /bin/sh incubator/extpipes
```