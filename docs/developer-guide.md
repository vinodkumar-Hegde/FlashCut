# DT-FlashCut Developer Guide

## Purpose

This document is for engineers who maintain DT-FlashCut or integrate another application with its APIs.

For the overall architecture and role boundaries, read `docs/team-handover.md` first.

## 1. Local prerequisites

DT-FlashCut local development is Docker-based.

Do not create a project `.venv` as part of the supported local workflow.

Required tools:

```text
Docker Desktop / Docker Engine with Compose
Git
Python 3 on the host for repository test scripts
AWS CLI when local AWS-backed flows are exercised
```

## 2. Local configuration

Start from:

```sh
cp .env.example .env
```

Populate only environment-specific local values.

For Docker on macOS/Linux, set the local container UID/GID using:

```sh
id -u
id -g
```

`LOCAL_CONTAINER_USER` should represent the host user/group expected by the Compose file.

Never commit `.env`.

Important local settings include:

```text
APP_ENV=local
AUTH_DISABLED=true
AWS_PROFILE
AWS_REGION
S3_BUCKET
DATABASE_URL
BEDROCK_MODEL_ID
QUICK_SUMMARY_QUEUE_URL
LEARNING_MATERIAL_QUEUE_URL
RENDER_QUEUE_URL
PRODUCTION_GATE_BUCKET
PRODUCTION_GATE_VIDEO_KEY
```

The Compose configuration supplies local PostgreSQL/Redis wiring where appropriate.

## 3. Start the application

Full local stack:

```sh
docker compose -f docker-compose.yml up -d --build
```

API-only stack:

```sh
docker compose -f docker-compose.api.yml up -d --build
```

Inspect status:

```sh
docker compose -f docker-compose.yml ps
```

Local endpoints:

```text
Web:      http://127.0.0.1:8080
API:      http://127.0.0.1:5002
Swagger:  http://127.0.0.1:5002/docs
Ready:    http://127.0.0.1:5002/health/ready
Live:     http://127.0.0.1:5002/health/live
```

Swagger is disabled when `APP_ENV=production`.

## 4. Health semantics

Liveness:

```http
GET /health/live
```

Liveness proves the process is serving HTTP.

Readiness:

```http
GET /health/ready
```

Readiness verifies:

- PostgreSQL connectivity,
- configured S3 bucket access,
- Redis connectivity when rate limiting is enabled.

A `503 {"status":"not_ready"}` means the API process exists but a required dependency is unavailable or misconfigured.

## 5. Source-video integration

An external product should not send arbitrary media URLs.

The supported source contract is:

```text
business selection
-> approved S3 bucket + key
-> POST /api/v1/videos/resolve
-> video_id
```

Request:

```json
{
  "bucket": "configured-source-bucket",
  "key": "configured/allowed/prefix/video.mp4"
}
```

Optional:

```json
{
  "expected_etag": "known-etag"
}
```

The exact object key must satisfy the environment's source prefix and tenant prefix.

## 6. Quick Summary integration

Create:

```http
POST /api/v1/quick-summaries
```

Body:

```json
{
  "video_id": "VIDEO_ID"
}
```

Use `Idempotency-Key`.

Poll:

```http
GET /api/v1/quick-summaries/{id}
```

Fetch completed result:

```http
GET /api/v1/quick-summaries/{id}/result
```

Do not use `/api/v1/summaries` for this feature. That route belongs to video editing.

## 7. Learning Materials integration

Create:

```http
POST /api/v1/learning-materials
```

Body:

```json
{
  "video_id": "VIDEO_ID",
  "notes_style": "standard",
  "include_mind_map": true,
  "include_flowchart": true
}
```

Poll:

```http
GET /api/v1/learning-materials/{id}
```

Fetch JSON:

```http
GET /api/v1/learning-materials/{id}/result
```

Fetch PDF:

```http
GET /api/v1/learning-materials/{id}/pdf
```

Supported note styles:

```text
standard
crisp
high_yield
```

## 8. Status handling

Quick Summary:

```text
waiting_for_transcript
queued
processing
completed
failed
```

Learning Materials:

```text
waiting_for_transcript
queued
processing
completed
partial
failed
```

Clients should not assume `202` means the work completed.

Clients should poll the status endpoint.

Result endpoints may return `409` before the result is ready.

## 9. Error handling

The API uses structured errors:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "..."
  },
  "request_id": "..."
}
```

Common HTTP meanings:

```text
401 authentication failure
403 tenant/source authorization rejection
404 resource/source not found
409 state, source-version, or idempotency conflict
422 invalid request
429 rate limited
500 internal error without stack trace exposure
503 dependency/readiness failure
```

Log the returned `request_id` in the caller so operations can correlate a client failure with server logs.

## 10. Authentication rules

Local development can disable auth.

Production cannot.

Production integration must send a Bearer JWT.

The API validates configured issuer, audience/client ID, token use, signing algorithm, subject claim, and tenant claim.

Do not add a request-body `tenant_id` as a shortcut.

Tenant identity must remain derived from the authenticated principal.

## 11. Data and S3 safety rules

When changing source handling:

- keep the configured bucket allowlist behavior,
- keep source-prefix enforcement,
- keep tenant-prefix enforcement,
- keep ETag/source-version checks,
- do not introduce arbitrary HTTP/HTTPS download-to-FFmpeg behavior,
- do not log presigned URLs, tokens, transcript bodies, or note bodies.

## 12. Generation reliability rules

When changing Quick Summary or Learning Materials:

- write job + outbox in one transaction,
- do not publish SQS before the database transaction is durable,
- preserve idempotency behavior,
- preserve tenant ownership,
- preserve worker attempt/heartbeat semantics,
- preserve DLQ behavior,
- do not make the HTTP POST wait for model completion.

## 13. Database migrations

Alembic is the migration system.

Current repository migration head is:

```text
0014
```

Do not edit an already-released migration to change production history.

Create a new numbered migration for schema changes.

Local migration status is validated by:

```sh
./scripts/production-grade-test.sh
```

Production/staging migration execution belongs to the deployment owner.

## 14. Main code map

API routers:

```text
api/app/api/videos.py
api/app/api/quick_summaries.py
api/app/api/learning_materials.py
api/app/api/summaries.py
api/app/api/selections.py
api/app/api/renders.py
api/app/api/render_assets.py
```

Generation services:

```text
api/app/services/quick_summary_service.py
api/app/services/learning_material_service.py
```

Workers:

```text
api/app/workers/generation_outbox_dispatcher.py
api/app/workers/generation_queue_worker.py
api/app/workers/quick_summary_worker.py
api/app/workers/learning_material_worker.py
api/app/workers/render_worker.py
```

Configuration/security:

```text
api/app/core/config.py
api/app/core/auth.py
api/app/core/security.py
api/app/core/observability.py
```

## 15. Required regression before handing a change to QA

Run:

```sh
./scripts/production-grade-test.sh
```

Expected:

```text
PASSED: 18
FAILED: 0
PRODUCTION GATE: PASS
```

Then run:

```sh
./scripts/generation-e2e-test.sh
```

Expected:

```text
GENERATION E2E: PASS
```

The generation gate creates real Quick Summary and Learning Materials jobs against the configured fixture.

## 16. Git hygiene

Do not stage everything blindly.

Review exact changes:

```sh
git status --short
git diff --check
git diff --stat
```

Stage only intended files.

Do not commit:

```text
.env
AWS credentials
private keys
Terraform plan files
local databases
generated PDFs/videos
temporary logs
backup/copy files
node_modules
```

## 17. Developer definition of done

A developer change is ready for handoff when:

- API contract impact is documented,
- tenant isolation is preserved,
- idempotency is preserved where applicable,
- migrations are added when required,
- local services are healthy,
- production gate passes,
- generation E2E passes when generation is affected,
- no secret/environment-specific values are committed,
- the working tree contains only intended changes,
- QA has a clear acceptance path.
