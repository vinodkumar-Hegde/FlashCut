#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
  git rev-parse --show-toplevel
)"

: "${AWS_PROFILE:?AWS_PROFILE must be set explicitly}"
: "${AWS_REGION:?AWS_REGION must be set explicitly}"

PROFILE="$AWS_PROFILE"
REGION="$AWS_REGION"

STAGING_DIR="$ROOT/infra/staging"

ACCOUNT_FILE="$STAGING_DIR/.expected-account-id"

BACKEND_FILE="$STAGING_DIR/backend.local.hcl"

LOCAL_STATE="$STAGING_DIR/terraform.tfstate"

if [[ -s "$LOCAL_STATE" ]]; then
  echo \
    "STOP: a local Terraform state file already exists."
  echo \
    "Review/migrate that state explicitly before configuring the remote backend."
  exit 1
fi

ACCOUNT_ID="$(
  aws \
    --profile "$PROFILE" \
    --region "$REGION" \
    sts get-caller-identity \
    --query Account \
    --output text
)"

echo
echo "AWS profile: $PROFILE"
echo "AWS region:  $REGION"
echo "AWS account: $ACCOUNT_ID"
echo

printf \
  "Type the AWS account ID above to authorize DT-FlashCut staging: "

read -r CONFIRM_ACCOUNT

if [[ "$CONFIRM_ACCOUNT" != "$ACCOUNT_ID" ]]; then
  echo "STOP: account confirmation did not match."
  exit 1
fi

printf '%s\n' \
  "$ACCOUNT_ID" \
  > "$ACCOUNT_FILE"

chmod 600 \
  "$ACCOUNT_FILE"

BUCKET="flashcut-terraform-state-${ACCOUNT_ID}-${REGION}"

echo
echo "Terraform state bucket:"
echo "$BUCKET"
echo

if aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  s3api head-bucket \
  --bucket "$BUCKET" \
  >/dev/null 2>&1
then
  echo "State bucket already exists."

else
  echo "Creating Terraform state bucket..."

  if [[ "$REGION" == "us-east-1" ]]; then
    aws \
      --profile "$PROFILE" \
      --region "$REGION" \
      s3api create-bucket \
      --bucket "$BUCKET" \
      >/dev/null

  else
    aws \
      --profile "$PROFILE" \
      --region "$REGION" \
      s3api create-bucket \
      --bucket "$BUCKET" \
      --create-bucket-configuration \
        "LocationConstraint=$REGION" \
      >/dev/null
  fi
fi

aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
    'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'

aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration \
    'Status=Enabled'

aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration \
    '{
      "Rules": [
        {
          "ApplyServerSideEncryptionByDefault": {
            "SSEAlgorithm": "AES256"
          }
        }
      ]
    }'

aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  s3api put-bucket-ownership-controls \
  --bucket "$BUCKET" \
  --ownership-controls \
    '{
      "Rules": [
        {
          "ObjectOwnership": "BucketOwnerEnforced"
        }
      ]
    }'

POLICY_FILE="$(
  mktemp
)"

trap \
  'rm -f "$POLICY_FILE"' \
  EXIT

cat > "$POLICY_FILE" <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::$BUCKET",
        "arn:aws:s3:::$BUCKET/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
POLICY

aws \
  --profile "$PROFILE" \
  --region "$REGION" \
  s3api put-bucket-policy \
  --bucket "$BUCKET" \
  --policy "file://$POLICY_FILE"

cat > "$BACKEND_FILE" <<BACKEND
bucket       = "$BUCKET"
key          = "staging/terraform.tfstate"
region       = "$REGION"
encrypt      = true
use_lockfile = true
BACKEND

echo
echo "Initializing encrypted remote Terraform state..."

"$ROOT/scripts/terraform.sh" \
  -chdir=infra/staging \
  init \
  -reconfigure \
  -backend-config=backend.local.hcl

echo
echo "PASS: remote Terraform backend initialized."
