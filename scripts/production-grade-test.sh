#!/usr/bin/env bash

set -uo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

export PYTHONUNBUFFERED=1

python3 \
  tests/production/gate.py

exit $?
