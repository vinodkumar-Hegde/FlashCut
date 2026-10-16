#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  git rev-parse --show-toplevel
)"

: "${AWS_PROFILE:?AWS_PROFILE must be set explicitly}"
: "${AWS_REGION:?AWS_REGION must be set explicitly}"

PROFILE="$AWS_PROFILE"
REGION="$AWS_REGION"

ACCOUNT_FILE="$ROOT/infra/staging/.expected-account-id"

if [[ ! -f "$ACCOUNT_FILE" ]]; then
  echo \
    "STOP: Terraform AWS account guard is not initialized."
  echo \
    "Run ./scripts/bootstrap-terraform-backend.sh first."
  exit 1
fi

EXPECTED_ACCOUNT="$(
  tr -d '[:space:]' \
    < "$ACCOUNT_FILE"
)"

if [[ ! "$EXPECTED_ACCOUNT" =~ ^[0-9]{12}$ ]]; then
  echo \
    "STOP: invalid Terraform account guard file."
  exit 1
fi

ACTUAL_ACCOUNT="$(
  aws \
    --profile "$PROFILE" \
    --region "$REGION" \
    sts get-caller-identity \
    --query Account \
    --output text
)"

if [[ "$ACTUAL_ACCOUNT" != "$EXPECTED_ACCOUNT" ]]; then
  echo "STOP: AWS account mismatch."
  echo "Expected: $EXPECTED_ACCOUNT"
  echo "Actual:   $ACTUAL_ACCOUNT"
  exit 1
fi

exec docker run \
  --rm \
  -v "$ROOT:/workspace" \
  -w /workspace \
  -v "$HOME/.aws:/root/.aws:ro" \
  -e "AWS_PROFILE=$PROFILE" \
  -e "AWS_REGION=$REGION" \
  -e "AWS_DEFAULT_REGION=$REGION" \
  -e "AWS_SDK_LOAD_CONFIG=1" \
  -e "TF_VAR_expected_aws_account_id=$EXPECTED_ACCOUNT" \
  -e "TF_VAR_aws_region=$REGION" \
  hashicorp/terraform:1.16.5 \
  "$@"
