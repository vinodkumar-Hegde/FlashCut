#!/usr/bin/env bash

set -euo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

export PYTHONUNBUFFERED=1

if [[ -f .env ]]; then
  while IFS='=' read -r key value
  do
    value="${value%$'\r'}"

    case "$key" in
      PRODUCTION_GATE_BUCKET|PRODUCTION_GATE_VIDEO_KEY)
        if [[ -z "${!key:-}" ]]; then
          export "$key=$value"
        fi
        ;;
    esac
  done < .env
fi

exec python3   tests/production/gate.py
