#
# 230327 pa: the Dockerfile is a full rework, to use the power of
# poetry, venv and wheels, the same way you work local
#
# inspiration: https://bmaingret.github.io/blog/2021-11-15-Docker-and-Poetry
#
# the same Dockerfile is used for extpipes-cli and bootstrap-cli, where only the top ARGs are different

# APP_WHEEL_NAME: poetry build automatically changes the name
# - there is no working ${APP_NAME//-/_} substitution logic in Dockerfile
ARG APP_WHEEL_NAME=extpipes_cli
# APP_NAME: matching the pyproject.toml "name" and "scripts"-hook!
ARG APP_NAME=extpipes-cli
ARG APP_PATH=/opt/$APP_NAME
ARG PYTHON_VERSION=3.10
ARG POETRY_VERSION=1.3.2

#
# Stage: staging
#
# gcr.io/distroless/python3-debian11 (runtime env is using 3.9 and that's important for native dependencies)
FROM python:${PYTHON_VERSION}-slim AS staging

# copy ATGs into stage
ARG APP_NAME
ARG APP_PATH
ARG POETRY_VERSION

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1
ENV \
    POETRY_VERSION=$POETRY_VERSION \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# python-slim image is missing curl, required for official poetry installation
RUN apt-get -y update; apt-get -y install curl

# Poetry setup
# RUN python3 -m pip install --upgrade pip
# RUN pip install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR $APP_PATH

COPY ./poetry.lock ./pyproject.toml README.md ./
# respecting .dockerignore and skips __pycache__ folders!
COPY ./src ./src

#
# Stage: development
#
FROM staging as development
ARG APP_NAME
ARG APP_PATH

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR $APP_PATH
RUN poetry install

ENTRYPOINT ["poetry", "run", "${APP_NAME}"]

#
# Stage: build
#
FROM staging as build
ARG APP_PATH

WORKDIR $APP_PATH
RUN poetry build --format wheel
# slim export without dev-dependencies (would need a `--with dev` parameter)
RUN poetry export --format requirements.txt --output requirements.txt --without-hashes

#
# Stage: production
#
FROM python:${PYTHON_VERSION}-slim as production
ARG APP_NAME
ARG APP_WHEEL_NAME
ARG APP_PATH

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

ENV \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Use build artifact wheel and install it with all dependencies
WORKDIR $APP_PATH
COPY --from=build $APP_PATH/dist/*.whl ./
COPY --from=build $APP_PATH/requirements.txt ./
RUN pip install ./$APP_WHEEL_NAME*.whl -r requirements.txt

# Entrypoint script - activate venv and awaits commandline
COPY ./docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
# make the ARG (only build time) available for docker run-time as ENV
ENV ENV_APP_NAME=${APP_NAME}
ENTRYPOINT ["/docker-entrypoint.sh", "$ENV_APP_NAME"]
