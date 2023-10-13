#!/bin/bash
set -e
cd "${0%/*}/.."

TAG="${VERSION:-latest}"
IMAGE="${IMAGE:-extpipes-cli}"

echo "Running image '$IMAGE:$TAG'"
echo "$(pwd)"

set +e
# adopt the parameters and config as you need
docker run \
  --mount type=bind,source=$(pwd)/configs/example-config-extpipesv3.yml,target=/etc/config.yaml,readonly \
  --entrypoint run \
  --env-file=.env_example \
  --rm \
  $IMAGE \
  --dry-run \
  deploy \
  /etc/config.yaml

set -e

RESULT=$?
exit $RESULT
