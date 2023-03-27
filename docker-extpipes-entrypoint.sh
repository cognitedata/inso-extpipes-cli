#!/bin/sh

set -e

# You can put other setup logic here
# Evaluating passed parameters to extpipes-cli:
eval "exec extpipes-cli $@"
