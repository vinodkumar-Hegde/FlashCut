#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  git rev-parse --show-toplevel
)"

PROFILE="${AWS_PROFILE:-dev}"
REGION="${AWS_REGION:-ap-south-1}"

exec docker run \
  --rm \
  -v "$ROOT:/workspace" \
  -w /workspace \
  -v "$HOME/.aws:/root/.aws:ro" \
  -e "AWS_PROFILE=$PROFILE" \
  -e "AWS_REGION=$REGION" \
  -e "AWS_DEFAULT_REGION=$REGION" \
  -e "AWS_SDK_LOAD_CONFIG=1" \
  hashicorp/terraform:1.16.5 \
  "$@"
