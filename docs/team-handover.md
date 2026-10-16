# DT-FlashCut Team Handover Guide

## Purpose

This is the master handover document for DT-FlashCut. It is intended for:

- application developers integrating DT-FlashCut,
- DevOps/platform engineers deploying and operating it,
- QA engineers validating a release,
- product/engineering leads who need to understand how the system works.

This guide explains the architecture, the two independent generation APIs, the existing video-editing workflow, integration boundaries, deployment requirements, QA gates, ownership, and the recommended team handoff process.

The detailed API contract remains in `docs/integration-api.md`.

## 1. What DT-FlashCut does

DT-FlashCut is a transcript-driven educational video platform.

It supports three separate product paths:

1. **Quick Summary** — generates a concise summary, key points, and topics for a video.
2. **Learning Materials** — generates Notes, optional Mind Map, optional Flow Chart, and a downloadable PDF.
3. **Video Editing / Rendering** — uses transcript-aware editing selections and renders an edited video, with optional intro/outro assets.

Quick Summary and Learning Materials are intentionally independent APIs. They do not reuse the editing-summary API.

## 2. High-level architecture

```text
                                  ┌────────────────────────────┐
Course / Subject / Topic          │ Integrating Application     │
        │                         │ maps business content to S3 │
        └────────────────────────>│ bucket + object key         │
                                  └──────────────┬─────────────┘
                                                 │
                                                 │ POST /api/v1/videos/resolve
                                                 v
┌──────────────────────────────────────────────────────────────────────┐
│                          DT-FlashCut API                              │
│                                                                      │
│  Authentication / tenant context / validation / idempotency          │
│                                                                      │
│  Quick Summary API      Learning Materials API      Editing APIs      │
└───────────┬────────────────────┬────────────────────────┬────────────┘
            │                    │                        │
            │ DB transaction     │ DB transaction         │
            v                    v                        v
      ┌───────────┐        ┌───────────┐           ┌──────────────┐
      │ job +     │        │ job +     │           │ transcript / │
      │ outbox    │        │ outbox    │           │ selection /  │
      └─────┬─────┘        └─────┬─────┘           │ render jobs  │
            │                    │                 └──────┬───────┘
            v                    v                        │
      Outbox dispatcher     Outbox dispatcher            v
            │                    │                  Render SQS
            v                    v                        │
   Quick Summary SQS     Learning Material SQS           v
            │                    │                 FFmpeg worker
            v                    v                        │
   Quick Summary worker   Learning Material worker       v
            │                    │                  generated S3
            └──────────┬─────────┘
                       v
                 persisted results

Supporting services:
- PostgreSQL: jobs, results, ownership, audit data, outboxes
- Redis: distributed rate limiting
- S3: source video, transcripts/output assets/render output
- AWS Transcribe: transcription when a transcript is not already available
- Amazon Bedrock: summary / notes / visual generation
- SQS + DLQ: asynchronous work delivery
- FFmpeg: video rendering
```

## 3. The most important integration rule

The business application owns the hierarchy:

```text
Course -> Subject -> Topic -> source media mapping
```

DT-FlashCut does **not** own Course, Subject, or Topic.

The integrating application resolves that selection to an approved S3 bucket and object key, then registers/resolves the object with DT-FlashCut:

```http
POST /api/v1/videos/resolve
Authorization: Bearer <token>
Content-Type: application/json

{
  "bucket": "configured-source-bucket",
  "key": "configured/allowed/prefix/video.mp4"
}
```

DT-FlashCut validates:

- the bucket is exactly the configured source bucket,
- the object key is inside the configured allowed prefix,
- in tenant-isolated production deployments, the key is inside the tenant-specific prefix,
- the object exists,
- the object is non-empty,
- the file extension is supported,
- an optional expected ETag still matches.

The response returns a DT-FlashCut `video_id`.

Every downstream API uses `video_id`; callers should not pass a raw S3 URL or presigned media URL as a render/generation input.

### Production tenant prefix

The reference staging Terraform currently configures:

```text
S3_VIDEO_PREFIX=videos/
S3_TENANT_PREFIX_TEMPLATE=videos/tenants/{tenant_id}/
```

Therefore the real production key supplied by an integrating application must match the environment's configured source-prefix policy. DevOps and the integration team must agree on this mapping before go-live.

## 4. Two independent generation APIs

### 4.1 Quick Summary API

Use Quick Summary when the caller needs only a short educational summary.

Create:

```http
POST /api/v1/quick-summaries
Authorization: Bearer <token>
Idempotency-Key: <unique-key>
Content-Type: application/json

{
  "video_id": "VIDEO_ID"
}
```

New work returns `202 Accepted`.

If the same request body is replayed with the same `Idempotency-Key`, DT-FlashCut returns the original job with:

```http
Idempotency-Replayed: true
```

Status:

```http
GET /api/v1/quick-summaries/{quick_summary_id}
```

Result:

```http
GET /api/v1/quick-summaries/{quick_summary_id}/result
```

A completed result contains:

```json
{
  "id": "JOB_ID",
  "status": "completed",
  "summary": "...",
  "key_points": ["...", "..."],
  "topics": ["...", "..."]
}
```

Typical status lifecycle:

```text
waiting_for_transcript -> queued -> processing -> completed
```

If a transcript already exists, the job may begin at `queued`.

A terminal generation failure is reported as `failed`.

The result endpoint returns a conflict while the job is not complete, so clients should poll the status endpoint first.

### 4.2 Learning Materials API

Use Learning Materials when the caller needs structured study content.

Create:

```http
POST /api/v1/learning-materials
Authorization: Bearer <token>
Idempotency-Key: <unique-key>
Content-Type: application/json

{
  "video_id": "VIDEO_ID",
  "notes_style": "standard",
  "include_mind_map": true,
  "include_flowchart": true
}
```

Supported `notes_style` values:

```text
standard
crisp
high_yield
```

Status:

```http
GET /api/v1/learning-materials/{learning_material_id}
```

JSON result:

```http
GET /api/v1/learning-materials/{learning_material_id}/result
```

PDF:

```http
GET /api/v1/learning-materials/{learning_material_id}/pdf
```

The JSON result contains:

```text
notes
mind_map
flowchart
component_status
component_errors
revision
status
```

A Learning Materials job can be:

```text
waiting_for_transcript
queued
processing
completed
partial
failed
```

`partial` means the core Notes generation succeeded but one or more requested optional visual components failed.

For enterprise/UAT certification in this repository, when Mind Map and Flow Chart were requested, QA treats `partial` as a failed acceptance result.

### 4.3 The two APIs do not depend on each other

Quick Summary is not a prerequisite for Learning Materials.

Learning Materials is not a prerequisite for Quick Summary.

Both independently accept the same `video_id`.

Both may reuse an existing transcript, or trigger/refresh transcription internally if a transcript is not yet available.

Both use their own job table, transactional outbox, SQS queue, DLQ, and worker.

This separation is intentional so the two workloads can scale and fail independently.

## 5. Existing video-editing workflow

Do not confuse Quick Summary with the editing-summary workflow.

Editing summary:

```text
/api/v1/summaries
```

Selection/review:

```text
/api/v1/selections
```

Rendering:

```text
/api/v1/renders
```

Intro/outro assets:

```text
/api/v1/render-assets
```

Editing flow:

```text
source video
  -> transcription
  -> editing summary
  -> draft selection
  -> manual/automatic review
  -> approved selection
  -> render job
  -> render SQS
  -> FFmpeg worker
  -> generated S3 output
```

Quick Summary must never be implemented by repurposing `/api/v1/summaries`.

## 6. Why the generation pipeline uses an outbox

Quick Summary and Learning Materials use a transactional outbox.

When the API accepts a create request, it writes the job and an outbox row in the same PostgreSQL transaction.

That prevents this failure mode:

```text
database commit succeeds
but queue publish fails
=> job is permanently lost
```

Instead:

```text
API transaction
  -> job + outbox persisted
  -> dispatcher publishes to SQS
  -> dedicated worker processes message
  -> final state persisted
```

The dispatcher can retry publishing.

Workers use processing attempts, heartbeats, queue visibility management, and job state transitions. SQS/DLQ remains the transport-level failure boundary.

## 7. Authentication and tenant isolation

Local Docker development can run with:

```text
APP_ENV=local
AUTH_DISABLED=true
LOCAL_TENANT_ID=local-development
```

Production must use authentication.

The application configuration enforces:

```text
APP_ENV=production
AUTH_DISABLED=false
AUTH_JWT_ISSUER=<issuer>
AUTH_JWT_AUDIENCE=<client id / audience>
AUTH_TENANT_CLAIM=custom:tenant_id
AUTH_SUBJECT_CLAIM=sub
RATE_LIMIT_ENABLED=true
REDIS_URL=<managed redis URL>
TRUSTED_HOSTS=<explicit hosts>
```

Production callers send:

```http
Authorization: Bearer <JWT>
```

Tenant identity is derived from the authenticated principal. The caller must not be allowed to choose an arbitrary trusted tenant ID in the request body.

All tenant-owned database resources are queried through tenant-aware repositories/session handling.

## 8. Idempotency contract

Use a unique `Idempotency-Key` when creating Quick Summary or Learning Materials jobs.

Safe retry:

```text
same key + same body -> original job is returned
```

Invalid reuse:

```text
same key + materially different body -> conflict
```

The client should generate the idempotency key before the first request and persist/reuse it for retries caused by timeouts or transient network failures.

Do not generate a new key for every retry of the same logical user action.

## 9. Client integration sequence

Recommended client flow:

```text
1. User chooses Course / Subject / Topic
2. Integrating application maps selection to approved S3 bucket + key
3. POST /api/v1/videos/resolve
4. Store returned video_id
5. Call Quick Summary and/or Learning Materials
6. Store returned job id
7. Poll GET job status
8. On completed, fetch result
9. For Learning Materials, optionally fetch PDF
```

A client should use bounded polling, for example every 2–5 seconds with a maximum overall timeout appropriate for the product.

Do not keep the original POST connection open waiting for model generation.

## 10. Example integration with curl

Set values in the shell; do not hardcode credentials in source:

```sh
BASE_URL="https://api.example.internal"
TOKEN="..."
SOURCE_BUCKET="..."
SOURCE_KEY="..."
```

Resolve source:

```sh
curl -sS \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "{
    \"bucket\":\"$SOURCE_BUCKET\",
    \"key\":\"$SOURCE_KEY\"
  }" \
  "$BASE_URL/api/v1/videos/resolve"
```

Quick Summary create:

```sh
curl -sS \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $REQUEST_ID" \
  -H "Content-Type: application/json" \
  --data "{\"video_id\":\"$VIDEO_ID\"}" \
  "$BASE_URL/api/v1/quick-summaries"
```

Learning Materials create:

```sh
curl -sS \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $REQUEST_ID" \
  -H "Content-Type: application/json" \
  --data "{
    \"video_id\":\"$VIDEO_ID\",
    \"notes_style\":\"standard\",
    \"include_mind_map\":true,
    \"include_flowchart\":true
  }" \
  "$BASE_URL/api/v1/learning-materials"
```

## 11. Repository map

Important application paths:

```text
api/app/api/quick_summaries.py
api/app/services/quick_summary_service.py
api/app/api/learning_materials.py
api/app/services/learning_material_service.py
api/app/services/video_service.py

api/app/workers/generation_outbox_dispatcher.py
api/app/workers/generation_queue_worker.py
api/app/workers/quick_summary_worker.py
api/app/workers/learning_material_worker.py
api/app/workers/render_worker.py

api/alembic/versions/0014_generation_outbox.py

tests/production/gate.py
scripts/production-grade-test.sh
scripts/generation-e2e-test.sh

docs/integration-api.md
docs/team-handover.md
docs/developer-guide.md
docs/devops-runbook.md
docs/qa-runbook.md
```

## 12. Ownership matrix

| Area | Application developers | Integration developers | DevOps/platform | QA |
|---|---|---|---|---|
| API behavior | Own | Consume | Support runtime | Validate |
| Course/Subject/Topic mapping | No | Own | No | Validate mapping |
| S3 source policy | Implement validation | Supply valid mapping | Own bucket/IAM/KMS/prefix config | Validate allow/deny |
| JWT/OIDC logic | Implement | Supply token | Own IdP/runtime config | Validate |
| PostgreSQL schema/migrations | Write migrations | No | Execute/operate | Verify head |
| SQS/DLQ/outbox code | Implement | No | Provision/monitor | Validate E2E |
| Container images | Provide Dockerfiles | No | Build/promote/deploy | Verify release |
| ECS/server sizing | No | No | Own | Observe |
| TLS/DNS/WAF | No | No | Own | Security verification |
| HA/backups/restore | No | No | Own | Validate runbook/evidence |
| Local regression | Own | Support | Optional | Own acceptance |
| Staging/prod certification | Support | Support | Own environment | Own sign-off |

## 13. Current handoff boundary

The application team handoff is considered complete when:

- the repository is clean,
- application code is pushed,
- migrations are present,
- Dockerfiles build,
- local production gate passes,
- generation E2E passes,
- API/integration documentation is current.

The application team does **not** own final staging/production activation.

DevOps owns:

- selecting the approved runtime platform,
- Terraform apply or equivalent infrastructure deployment,
- image promotion,
- one-off migration execution,
- secret configuration,
- runtime IAM,
- scaling,
- DNS/TLS/WAF,
- RDS/Redis HA and backups,
- monitoring/alerts,
- rollback,
- production cutover.

The repository contains a reference AWS/ECS staging implementation. It is deployment material, not a mandate that production must use the same sizing or topology.

## 14. Release evidence to hand over

For each release, the team should record:

```text
Git commit SHA
API image tag/digest
Render image tag/digest
Migration head
Terraform/infra plan reference
Migration execution result
QA gate result
Generation E2E result
Staging endpoint tested
QA sign-off
Deployment owner
Rollback release
```

Do not put access tokens, secret values, database passwords, AWS access keys, or presigned URLs into handoff documents or CI logs.

## 15. Five-minute team explanation

Use this talk track in a handoff meeting:

> DT-FlashCut receives an approved S3 video reference from the integrating system. The integrating system owns Course, Subject, and Topic, and maps them to an S3 bucket/key. DT-FlashCut validates the source and returns a `video_id`.
>
> From that point there are two independent generation APIs. Quick Summary returns summary, key points, and topics. Learning Materials returns Notes, optional Mind Map, optional Flow Chart, and a PDF. They do not call each other and they do not use the editing-summary API.
>
> Both generation APIs are asynchronous. The create call writes a job plus a transactional outbox record. A dispatcher publishes to a dedicated SQS queue, and a dedicated worker produces the result. Clients poll the job status and fetch the result after completion.
>
> The existing editing flow remains separate: transcription, editing summary, review/selection, and FFmpeg rendering. Intro/outro are optional render assets.
>
> Production uses JWT/OIDC tenant identity, tenant-aware database access, S3 source-prefix enforcement, Redis rate limiting, audit logging, idempotency, SQS/DLQ, and managed AWS dependencies.
>
> Developers own application behavior and contracts. Integration developers own Course/Subject/Topic-to-S3 mapping. DevOps owns deployment and production infrastructure. QA owns release acceptance using the production and generation E2E gates plus post-deploy checks.

## 16. Related documents

Read these next:

- `docs/developer-guide.md` — developer setup, code map, integration rules
- `docs/devops-runbook.md` — deployment/runtime contract and DevOps-owned sequence
- `docs/qa-runbook.md` — QA test plan, acceptance criteria, evidence
- `docs/integration-api.md` — API contract details
