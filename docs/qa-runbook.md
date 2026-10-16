# DT-FlashCut QA Runbook

## Purpose

This is the release-validation plan for DT-FlashCut.

QA should validate both application correctness and the separation of the two generation APIs from the video-editing workflow.

## 1. QA release inputs

QA should receive:

```text
Git release SHA
environment/base URL
release image identifiers/digests
expected migration head
test tenant/user
approved S3 fixture bucket + key
authentication method/token acquisition instructions
deployment/migration result from DevOps
known limitations
```

Do not request raw production secrets in tickets or chat.

## 2. Local production gate

Run:

```sh
./scripts/production-grade-test.sh
```

Current expected result:

```text
PASSED: 18
FAILED: 0
TOTAL : 18
PRODUCTION GATE: PASS
```

The gate validates:

```text
compose.configuration
containers.required-services
redis.health
api.readiness
database.migration-head
security.headers
security.request-size
security.rate-limit
security.rate-limit-recovery
s3.resolve-valid
s3.wrong-bucket
s3.prefix-isolation
s3.stale-etag
idempotency.notes-concurrency
idempotency.selection-concurrency
audit.security-events
logging.no-secrets
security.no-stacktrace
```

The expected migration head is `0014`.

This gate is a controlled application regression gate; it is not a substitute for platform penetration testing, load testing, backup testing, or production readiness review.

## 3. Generation E2E gate

Run locally using `.env` fixture values:

```sh
./scripts/generation-e2e-test.sh
```

Expected:

```text
PASS api.readiness
PASS api.contract-separation
PASS video.resolve
PASS quick-summary.create-idempotency
PASS learning-material.create-idempotency
PASS async.workers-completed
PASS quick-summary.result
PASS learning-material.result
PASS learning-material.pdf
GENERATION E2E: PASS
```

For authenticated staging:

```sh
GENERATION_GATE_BASE_URL="$STAGING_BASE_URL" \
GENERATION_GATE_BEARER_TOKEN="$STAGING_BEARER_TOKEN" \
GENERATION_GATE_BUCKET="$STAGING_SOURCE_BUCKET" \
GENERATION_GATE_VIDEO_KEY="$STAGING_SOURCE_KEY" \
./scripts/generation-e2e-test.sh
```

Use secure CI/runtime secret injection for the bearer token.

## 4. Quick Summary acceptance

### Create

Request:

```http
POST /api/v1/quick-summaries
Idempotency-Key: <key>

{
  "video_id": "VIDEO_ID"
}
```

Acceptance:

- new request returns `202`,
- response contains non-empty job `id`,
- status is a valid asynchronous state,
- tenant cannot access another tenant's job.

### Polling

```http
GET /api/v1/quick-summaries/{id}
```

Acceptance:

- job progresses without client keeping the POST open,
- attempt count increases when processed,
- terminal success is `completed`,
- terminal generation failure is `failed`.

### Result

```http
GET /api/v1/quick-summaries/{id}/result
```

Acceptance on success:

- `status=completed`,
- `summary` is non-empty,
- `key_points` is non-empty,
- `topics` is non-empty.

Before completion, result access should not incorrectly return a successful final result.

## 5. Learning Materials acceptance

### Create

```http
POST /api/v1/learning-materials
Idempotency-Key: <key>

{
  "video_id": "VIDEO_ID",
  "notes_style": "standard",
  "include_mind_map": true,
  "include_flowchart": true
}
```

Acceptance:

- new request returns `202`,
- job ID is non-empty,
- requested component flags are reflected in job state.

Test all valid note styles in functional QA:

```text
standard
crisp
high_yield
```

### Result

```http
GET /api/v1/learning-materials/{id}/result
```

For the full enterprise scenario with both visuals requested, require:

```text
status=completed
notes non-empty
mind_map non-empty
flowchart non-empty
component_status.notes=completed
component_status.mind_map=completed
component_status.flowchart=completed
component_errors empty
```

If the status is `partial`, record which optional component failed. For the full acceptance scenario, `partial` is a QA failure.

### PDF

```http
GET /api/v1/learning-materials/{id}/pdf
```

Acceptance:

- HTTP succeeds after result readiness,
- content is a valid PDF,
- file is non-empty,
- PDF corresponds to the requested learning material,
- no internal filesystem/S3 secret information is exposed.

## 6. Idempotency acceptance

For each generation API:

1. Create with a unique key.
2. Repeat the same body with the same key.
3. Verify the same job ID is returned.
4. Verify `Idempotency-Replayed: true`.
5. Reuse the key with a materially different body.
6. Verify the API rejects the conflict.

This protects against duplicate work caused by network/client retries.

## 7. Source-resolution acceptance

Validate:

### Valid source

```http
POST /api/v1/videos/resolve
```

Expected:

- `200` existing or `201` newly registered,
- response contains `video_id`, filename/name, ETag.

### Wrong bucket

Expected:

```text
403 source bucket not allowed
```

### Key outside allowed tenant/prefix

Expected:

```text
rejected
```

### Missing object

Expected:

```text
404
```

### Stale expected ETag

Expected:

```text
409 source version mismatch
```

### Unsupported extension

Expected:

```text
rejected
```

QA should use approved fixtures and should not test with arbitrary public URLs.

## 8. Authentication/tenant tests

In authenticated staging:

- no token -> `401`,
- invalid/expired token -> `401`,
- valid token -> authorized behavior,
- tenant A cannot read tenant B resources,
- tenant A cannot resolve tenant B source prefix,
- request body cannot override authenticated tenant identity.

Capture request IDs for failed cases.

## 9. Editing regression

Because the generation APIs were added without replacing existing editing behavior, QA must run an editing smoke test:

```text
resolve source video
-> obtain/reuse transcript
-> editing summary
-> create selection
-> modify manual timestamp/word selection if applicable
-> approve selection
-> render
-> poll render status
-> fetch final render result
```

Verify Quick Summary changes did not alter `/api/v1/summaries`.

Verify Learning Materials changes did not alter selection/render behavior.

## 10. Intro/outro regression

When render assets are in scope:

- upload/complete intro asset,
- upload/complete outro asset,
- preview metadata,
- render using intro/outro IDs,
- verify resulting output contains expected boundaries,
- verify asset ownership is tenant-scoped,
- verify size/duration/type restrictions.

## 11. Security regression

QA/application security checks should include:

```text
request body limit
security headers
trusted-host behavior
rate limiting
rate-limit recovery
no stack trace returned to client
no secret/token in logs
audit event generation
tenant isolation
source bucket/prefix enforcement
```

Production configuration must not run with `AUTH_DISABLED=true`.

## 12. Readiness tests

```http
GET /health/live
GET /health/ready
```

Acceptance:

```text
live -> 200 while process is alive
ready -> 200 only when required dependencies are available
```

Readiness depends on PostgreSQL, S3, and Redis when rate limiting is enabled.

A dependency failure should produce `503 not_ready`, not a false green readiness response.

## 13. Queue/worker acceptance

QA + DevOps jointly verify:

- Quick Summary queue is independent,
- Learning Materials queue is independent,
- dispatcher is running,
- each worker consumes the correct queue,
- messages do not remain indefinitely visible/in-flight,
- successful jobs are persisted,
- DLQ is empty after normal happy-path tests,
- worker failures are observable.

Do not assume an API `202` means the worker completed.

## 14. Failure-path scenarios

At minimum validate representative failures:

```text
invalid video_id
source missing
source version changed
invalid notes style
result fetched too early
authentication missing
tenant mismatch
rate limit exceeded
generation worker failure/retry
optional visual failure -> partial
render failure
dependency outage -> readiness 503
```

## 15. Post-deploy smoke test

After DevOps deploys:

1. Verify release SHA/image.
2. Verify migration head.
3. Verify `/health/live`.
4. Verify `/health/ready`.
5. Resolve an approved fixture.
6. Run Quick Summary E2E.
7. Run Learning Materials E2E including PDF.
8. Verify idempotency replay.
9. Run editing smoke test.
10. Check worker logs.
11. Check SQS/DLQ health.
12. Check audit logs for expected events.
13. Check no sensitive values leaked.
14. Record sign-off evidence.

## 16. QA evidence template

Use this structure:

```text
Environment:
Release SHA:
API image digest:
Render image digest:
Migration head:
Tester:
Date/time:

Production gate:
Generation E2E:
Auth/tenant:
Source resolve:
Quick Summary:
Learning Materials:
PDF:
Editing regression:
Render regression:
Rate limiting/security:
Queue/DLQ:
Log review:

Defects:
Waivers:
Final status: PASS / FAIL
```

## 17. Release blocking criteria

QA should block release if any of these occur:

- migration head does not match release,
- readiness is not stable,
- cross-tenant access succeeds,
- arbitrary/disallowed source object is accepted,
- Quick Summary and Learning Materials routes are mixed/reused incorrectly,
- idempotent replay creates duplicates,
- required Learning Materials components fail in the full acceptance scenario,
- generated PDF is invalid,
- editing/render regression is broken,
- production authentication is disabled,
- secrets/tokens appear in logs,
- DLQ/backlog shows unexplained failures,
- production gate fails,
- generation E2E fails.

## 18. QA sign-off boundary

Application tests prove the software release behaves as intended.

Platform production readiness also requires DevOps evidence for:

```text
HA
backup/restore
capacity/load
security perimeter
TLS/DNS/WAF
monitoring/alerts
deployment/rollback
image security policy
```

QA should not mark those controls as passed based only on the local application gates.
