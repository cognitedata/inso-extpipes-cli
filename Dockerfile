# gcr.io/distroless/python3-debian11 (runtime env is using 3.9 and that's important for native dependencies)
FROM python:3.9-slim AS builder

WORKDIR /

ENV PYTHONUNBUFFERED=1

# Poetry setup
RUN python3 -m pip install --upgrade pip
RUN pip install poetry==1.8.3
RUN poetry config virtualenvs.create false

COPY poetry.lock .
COPY pyproject.toml .

RUN poetry config virtualenvs.create false
RUN poetry export -f requirements.txt --output requirements.txt
RUN pip install --target=/app -r requirements.txt --no-deps

# Keep the same folder structure for imports
COPY incubator/extpipes_cli/ /app/incubator/extpipes_cli/

# A distroless container image with Python and some basics like SSL certificates
# https://github.com/GoogleContainerTools/distroless
FROM gcr.io/distroless/python3-debian11
COPY --from=builder /app /app
ENV PYTHONPATH /app
ENTRYPOINT [ "python", "/app/incubator/extpipes_cli/__main__.py" ]
