# DT-FlashCut DevOps / Platform Runbook

## Purpose

This document defines the deployment contract for DT-FlashCut.

DevOps/platform engineering owns the actual staging and production deployment.

The repository includes an AWS/ECS/Terraform staging implementation as a reference deployment. Production sizing, HA topology, security controls, and deployment strategy remain platform-team decisions.

## 1. Application runtime components

DT-FlashCut requires these logical runtime roles:

```text
API
editing-summary worker
notes worker
render worker
generation outbox dispatcher
Quick Summary worker
Learning Materials worker
database migration task
```

The API, editing-summary worker, notes worker, dispatcher, Quick Summary worker, Learning Materials worker, and migration task can use the API image.

The render worker uses the render image because it includes FFmpeg.

## 2. External dependencies

Required platform dependencies:

```text
PostgreSQL
Redis
S3-compatible AWS S3 source/output storage
SQS queues and DLQs
AWS Transcribe
Amazon Bedrock
JWT/OIDC identity provider
central logs/metrics/alerts
```

The reference AWS staging Terraform provisions these dependencies.

## 3. Production configuration requirements

Production application configuration must satisfy:

```text
APP_ENV=production
AUTH_DISABLED=false
AUTH_JWT_ISSUER=<OIDC/JWT issuer>
AUTH_JWT_AUDIENCE=<expected audience/client>
AUTH_TENANT_CLAIM=custom:tenant_id
AUTH_SUBJECT_CLAIM=sub
AUTH_JWT_AUDIENCE_CLAIM=client_id
AUTH_JWT_TOKEN_USE=access
AUTH_JWT_ALGORITHMS=RS256

AWS_REGION=<region>

S3_BUCKET=<approved source/output bucket>
S3_VIDEO_PREFIX=<source prefix>
S3_TENANT_PREFIX_TEMPLATE=<tenant-isolated prefix template>
S3_OUTPUT_PREFIX=<generated output prefix>
S3_TRANSCRIPT_PREFIX=<transcript prefix>
S3_RENDER_ASSET_PREFIX=<render asset prefix>

DATABASE_URL=<secret>
REDIS_URL=<secret>
RATE_LIMIT_ENABLED=true
TRUSTED_HOSTS=<explicit hosts>

BEDROCK_REGION=<region>
BEDROCK_MODEL_ID=<approved model>

QUICK_SUMMARY_QUEUE_URL=<queue>
LEARNING_MATERIAL_QUEUE_URL=<queue>
RENDER_QUEUE_URL=<queue>
```

Do not use developer AWS profiles inside deployed workloads. Use workload/task IAM roles.

Do not put database or Redis credentials in image layers or source control.

## 4. IAM/runtime permissions

Runtime identities require only the permissions needed by their workloads.

The application uses:

```text
S3 list/location/get/put/delete as appropriate
SQS send/receive/delete/get-attributes/change-visibility
Transcribe start/get
Bedrock invoke-model
Secrets Manager read by execution/runtime configuration
CloudWatch/logging permissions through the platform
```

Production should split roles further if organizational least-privilege policy requires it.

Cross-account source buckets may also require:

```text
bucket policy
KMS decrypt permission
source account trust policy
```

## 5. Container build contract

Use immutable release identifiers.

Recommended:

```sh
RELEASE_SHA="$(git rev-parse HEAD)"
```

API image:

```sh
docker buildx build \
  --platform linux/amd64 \
  --file api/Dockerfile \
  --tag "$API_IMAGE:$RELEASE_SHA" \
  --provenance=true \
  --sbom=true \
  --push \
  api
```

Render image:

```sh
docker buildx build \
  --platform linux/amd64 \
  --file api/Dockerfile.render-worker \
  --tag "$RENDER_IMAGE:$RELEASE_SHA" \
  --provenance=true \
  --sbom=true \
  --push \
  api
```

Production promotion should prefer immutable digest or immutable SHA tag.

Do not deploy a mutable `latest`/`staging` tag as the release identity.

Run registry vulnerability scanning according to company policy before promotion.

## 6. Reference staging preflight

The repository provides:

```sh
AWS_PROFILE="$AWS_PROFILE" \
AWS_REGION="$AWS_REGION" \
STAGING_SOURCE_BUCKET="$STAGING_SOURCE_BUCKET" \
STAGING_SOURCE_KEY="$STAGING_SOURCE_KEY" \
./scripts/staging-preflight.sh
```

This checks repository cleanliness, Docker availability, AWS access to required services, source-video readability/protection, and the local production gate.

The script is a preflight, not production certification.

## 7. Reference Terraform workflow

The Terraform wrapper performs an AWS-account guard and runs Terraform in Docker.

Plan:

```sh
RELEASE_SHA="$(git rev-parse HEAD)"

./scripts/terraform.sh \
  -chdir=infra/staging \
  plan \
  -var="bootstrap_mode=true" \
  -var="image_tag=$RELEASE_SHA" \
  -out=release.tfplan \
  -no-color
```

Review the saved plan before apply.

When `bootstrap_mode=true`, reference ECS services remain at zero while images/task definitions/migrations are prepared.

Apply is a DevOps-owned action:

```sh
./scripts/terraform.sh \
  -chdir=infra/staging \
  apply \
  -no-color \
  release.tfplan
```

Never apply an old saved plan after source/config/state has changed. Generate and review a fresh plan.

## 8. Database migration sequence

Current repository Alembic head:

```text
0014
```

The reference migration task definition runs:

```text
alembic -c /app/alembic.ini upgrade head
```

Required deployment sequence:

```text
1. Pin/release immutable application images
2. Keep application services stopped or otherwise migration-safe
3. Run one-off migration task
4. Wait for task completion
5. Require exit code 0
6. Verify Alembic/database is at expected head
7. Only then activate application services
```

Migration execution belongs to DevOps.

Capture the task/run identifier, image digest, exit code, and logs as release evidence.

## 9. Service activation sequence

A safe generic sequence after successful migration is:

```text
1. generation workers / render worker / existing workers
2. generation outbox dispatcher
3. API
4. load balancer/route exposure or traffic shift
```

Exact ordering can be adapted by the platform team because workers are queue-driven and should be safe to start before producers.

Before traffic is accepted, require:

```http
GET /health/live  -> 200
GET /health/ready -> 200 {"status":"ready"}
```

Readiness depends on PostgreSQL, S3, and Redis when rate limiting is enabled.

## 10. Post-deploy verification

Run the normal production gate where applicable:

```sh
./scripts/production-grade-test.sh
```

Run generation E2E with staging configuration:

```sh
GENERATION_GATE_BASE_URL="$STAGING_BASE_URL" \
GENERATION_GATE_BEARER_TOKEN="$STAGING_BEARER_TOKEN" \
GENERATION_GATE_BUCKET="$STAGING_SOURCE_BUCKET" \
GENERATION_GATE_VIDEO_KEY="$STAGING_SOURCE_KEY" \
./scripts/generation-e2e-test.sh
```

The token and fixture values must come from secure environment/CI secrets, not Git.

## 11. Queue/DLQ monitoring

Monitor separately:

```text
render queue
Quick Summary queue
Learning Materials queue
corresponding DLQs
```

Important metrics:

```text
ApproximateNumberOfMessagesVisible
ApproximateNumberOfMessagesNotVisible
ApproximateAgeOfOldestMessage
DLQ visible messages
worker desired/running count
worker restart/failure count
job failure rates
```

Quick Summary and Learning Materials are intentionally separate scaling units.

A backlog in one should not require scaling the other.

## 12. Logging and observability

The application emits structured logs and request IDs.

Operational logs must not contain:

```text
Authorization headers
JWT values
AWS secrets
database credentials
Redis credentials
presigned URLs
full transcript bodies
full generated note bodies
```

Retain enough metadata for:

```text
request ID
tenant-safe identifiers
route
status code
latency
job ID
worker state transition
error code
```

## 13. Production infrastructure decisions owned by DevOps

The provided staging defaults are intentionally small and are not production sizing guidance.

Production decisions include:

```text
RDS instance size
RDS Multi-AZ / failover
backup retention and restore testing
Redis size / replication / failover
NAT/network HA
container/task CPU and memory
worker min/max counts
autoscaling thresholds
ALB/ingress design
TLS certificate and custom domain
WAF
CloudFront/origin protection if used
S3 CORS for browser presigned uploads where required
secret rotation
deployment strategy
rollback strategy
CI/CD
image signing/scanning/SBOM policy
alert destinations
log retention
capacity/load testing
```

## 14. Production source-bucket contract

The API requires source bucket equality with configured `S3_BUCKET`.

The key must satisfy the configured allowed source prefix.

If `S3_TENANT_PREFIX_TEMPLATE` is configured, tenant context further restricts the key.

DevOps must align:

```text
S3 bucket policy
task/workload IAM
KMS key policy if SSE-KMS
configured S3_BUCKET
configured source prefix
configured tenant prefix
integration team's Course/Subject/Topic mapping
```

## 15. Rollback principles

Application rollback must be planned together with database compatibility.

Before release, identify:

```text
previous application image digest
previous render image digest
database migration compatibility
rollback/roll-forward decision
queue messages already produced by the new version
```

Do not blindly run Alembic downgrade in production.

Prefer backward-compatible migrations and application roll-forward where possible.

If a migration is not backward compatible, document the specific rollback plan before deployment.

## 16. Reference AWS/ECS status

The repository's staging Terraform currently models ECS Fargate.

This is a reference deployment.

DevOps may replace it with another approved platform if the following contracts are preserved:

```text
HTTP API on container port 5001
PostgreSQL access
Redis access
S3/IAM access
SQS worker connectivity
Transcribe/Bedrock access
independent worker processes
FFmpeg-capable render runtime
secret injection
health checks
central logs
migration execution
```

## 17. DevOps acceptance checklist

Before production traffic:

- immutable images are promoted,
- image scans meet policy,
- secrets are injected securely,
- migrations completed successfully,
- API readiness is green,
- workers are stable,
- queues/DLQs are healthy,
- authentication is enabled,
- tenant claim mapping is correct,
- S3 tenant/source policy is verified,
- rate limiting is enabled,
- TLS/DNS/WAF requirements are met,
- backups and restore procedure exist,
- monitoring/alerts are connected,
- QA staging sign-off is complete,
- rollback release is identified.

## 18. Handoff boundary

The application team supplies:

```text
source code
Dockerfiles
Alembic migrations
Terraform reference implementation
integration contract
regression gates
generation E2E gate
```

DevOps supplies:

```text
approved production topology
deployment pipeline
runtime secrets/IAM
migration execution
service activation
monitoring/HA/backups
staging and production release
```
