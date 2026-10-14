#!/usr/bin/env bash

set -uo pipefail

export AWS_PAGER=""

PROFILE="${AWS_PROFILE:-dev}"
REGION="${AWS_REGION:-ap-south-1}"

SOURCE_BUCKET="${STAGING_SOURCE_BUCKET:-transcript-video-prototype-dev}"
SOURCE_KEY="${STAGING_SOURCE_KEY:-videos/Ortho-Demo.mp4}"

TMP_DIR="$(
  mktemp -d
)"

trap '
  rm -rf "$TMP_DIR"
' EXIT

PASSED=0
FAILED=0


pass() {
  PASSED=$((PASSED + 1))

  printf 'PASS  %s\n' "$1"
}


fail() {
  FAILED=$((FAILED + 1))

  printf 'FAIL  %s\n' "$1"

  if [ -n "${2:-}" ]; then
    printf '      %s\n' "$2"
  fi
}


aws_check() {
  NAME="$1"
  shift

  ERR_FILE="$TMP_DIR/error"

  if aws \
    --profile "$PROFILE" \
    --region "$REGION" \
    "$@" \
    >/dev/null \
    2>"$ERR_FILE"
  then
    pass "$NAME"
  else
    ERROR="$(
      head -3 "$ERR_FILE" \
      | tr '\n' ' '
    )"

    fail \
      "$NAME" \
      "$ERROR"
  fi
}


printf '\n'
printf '%s\n' \
  '===================================================================='
printf '%s\n' \
  'DT-FlashCut AWS Staging Production Preflight'
printf '%s\n' \
  '===================================================================='
printf 'AWS profile : %s\n' "$PROFILE"
printf 'AWS region  : %s\n' "$REGION"
printf '\n'


# --------------------------------------------------
# Repository
# --------------------------------------------------

if [ -z "$(
  git status --porcelain
)" ]
then
  pass \
    "repository.clean"
else
  fail \
    "repository.clean" \
    "Working tree is not clean."
fi


# --------------------------------------------------
# Docker
# --------------------------------------------------

if docker info \
  >/dev/null \
  2>&1
then
  pass \
    "docker.available"
else
  fail \
    "docker.available" \
    "Docker daemon is unavailable."
fi


# --------------------------------------------------
# AWS identity
# --------------------------------------------------

IDENTITY_FILE="$TMP_DIR/identity.json"

if aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  sts \
  get-caller-identity \
  >"$IDENTITY_FILE" \
  2>"$TMP_DIR/error"
then
  pass \
    "aws.credentials"

  python3 \
    - "$IDENTITY_FILE" \
    <<'PY'
import json
import sys

with open(
    sys.argv[1],
    encoding="utf-8",
) as handle:
    data = json.load(
        handle
    )

account = str(
    data.get(
        "Account",
        "",
    )
)

if len(account) >= 8:
    account = (
        account[:4]
        + "****"
        + account[-4:]
    )

print(
    "      AWS account: "
    + account
)
PY

else
  ERROR="$(
    head -3 "$TMP_DIR/error" \
    | tr '\n' ' '
  )"

  fail \
    "aws.credentials" \
    "$ERROR"
fi


# --------------------------------------------------
# Regional infrastructure permissions
# --------------------------------------------------

aws_check \
  "aws.ec2" \
  ec2 \
  describe-availability-zones \
  --filters \
  Name=state,Values=available

aws_check \
  "aws.ecr" \
  ecr \
  describe-repositories \
  --max-results 1

aws_check \
  "aws.ecs" \
  ecs \
  list-clusters \
  --max-results 1

aws_check \
  "aws.rds" \
  rds \
  describe-db-instances \
  --max-records 20

aws_check \
  "aws.elasticache" \
  elasticache \
  describe-replication-groups \
  --max-records 20

aws_check \
  "aws.cognito" \
  cognito-idp \
  list-user-pools \
  --max-results 1

aws_check \
  "aws.secrets-manager" \
  secretsmanager \
  list-secrets \
  --max-results 1

aws_check \
  "aws.cloudwatch-logs" \
  logs \
  describe-log-groups \
  --limit 1

aws_check \
  "aws.sqs" \
  sqs \
  list-queues \
  --max-results 1

aws_check \
  "aws.transcribe" \
  transcribe \
  list-transcription-jobs \
  --max-results 1

aws_check \
  "aws.iam" \
  iam \
  list-roles \
  --max-items 1


# --------------------------------------------------
# CloudFront
#
# We will use its AWS-managed HTTPS domain for
# staging, so no custom domain/certificate is
# required for the first certification environment.
# --------------------------------------------------

aws_check \
  "aws.cloudfront" \
  cloudfront \
  list-distributions \
  --max-items 1


# --------------------------------------------------
# Bedrock access
# --------------------------------------------------

aws_check \
  "aws.bedrock" \
  bedrock \
  list-inference-profiles \
  --type-equals SYSTEM_DEFINED \
  --max-results 100


# --------------------------------------------------
# Existing source video
# --------------------------------------------------

HEAD_FILE="$TMP_DIR/source-head.json"

if aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  s3api \
  head-object \
  --bucket "$SOURCE_BUCKET" \
  --key "$SOURCE_KEY" \
  >"$HEAD_FILE" \
  2>"$TMP_DIR/error"
then
  pass \
    "source-video.readable"

  python3 \
    - "$HEAD_FILE" \
    <<'PY'
import json
import sys

with open(
    sys.argv[1],
    encoding="utf-8",
) as handle:
    data = json.load(
        handle
    )

size = int(
    data.get(
        "ContentLength",
        0,
    )
)

etag = str(
    data.get(
        "ETag",
        "",
    )
).strip('"')

print(
    "      Source bytes: "
    + str(size)
)

if etag:
    print(
        "      Source ETag : "
        + etag
    )
PY

else
  ERROR="$(
    head -3 "$TMP_DIR/error" \
    | tr '\n' ' '
  )"

  fail \
    "source-video.readable" \
    "$ERROR"
fi


# --------------------------------------------------
# Source bucket protection checks
# --------------------------------------------------

aws_check \
  "source-bucket.encryption-readable" \
  s3api \
  get-bucket-encryption \
  --bucket "$SOURCE_BUCKET"

aws_check \
  "source-bucket.public-access-config-readable" \
  s3api \
  get-public-access-block \
  --bucket "$SOURCE_BUCKET"


# --------------------------------------------------
# Local production gate still green
# --------------------------------------------------

if ./scripts/production-grade-test.sh \
  >"$TMP_DIR/local-gate.log" \
  2>&1
then
  pass \
    "local-production-gate"
else
  fail \
    "local-production-gate" \
    "Local 18-test gate failed."

  tail -30 \
    "$TMP_DIR/local-gate.log"
fi


printf '\n'
printf '%s\n' \
  '--------------------------------------------------------------------'
printf 'PASSED: %s\n' "$PASSED"
printf 'FAILED: %s\n' "$FAILED"
printf 'TOTAL : %s\n' "$((PASSED + FAILED))"
printf '\n'

if [ "$FAILED" -eq 0 ]
then
  printf '%s\n' \
    'STAGING PREFLIGHT: PASS'
else
  printf '%s\n' \
    'STAGING PREFLIGHT: FAIL'
fi

printf '%s\n' \
  '===================================================================='

if [ "$FAILED" -eq 0 ]
then
  exit 0
fi

exit 1
