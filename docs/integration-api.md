# DT-FlashCut Integration Contract

## Scope

This document defines the application-integration contract for DT-FlashCut. It covers source-video resolution, Quick Summary, Learning Materials, video editing, rendering, authentication, tenant isolation, asynchronous processing, and handoff verification.

## Source-video ownership boundary

The integrating application owns its business hierarchy, for example:

`Course -> Subject -> Topic -> S3 bucket/object key`

DT-FlashCut does not accept arbitrary remote media URLs as trusted render inputs. The integration layer supplies an approved S3 bucket and object key to:

`POST /api/v1/videos/resolve`

Request:

```json
{
  "bucket": "COURSE_CONTENT_BUCKET",
  "key": "courses/subject/topic/video.mp4"
}
```

An optional `expected_etag` may be supplied for source-version validation.

A successful request returns `200` for an existing tenant-owned video or `201` when a new video record is registered. The response includes the DT-FlashCut `video_id`; downstream workflows use this identifier rather than an S3 URL.

## Quick Summary API

Quick Summary is independent of the editing-summary workflow.

Create:

`POST /api/v1/quick-summaries`

```json
{
  "video_id": "VIDEO_ID"
}
```

Clients should send a unique `Idempotency-Key` header when creating a job.

A new job returns `202 Accepted`. Replaying the same request with the same idempotency key returns the original job and `Idempotency-Replayed: true`.

Status:

`GET /api/v1/quick-summaries/{quick_summary_id}`

Result:

`GET /api/v1/quick-summaries/{quick_summary_id}/result`

The result endpoint is available after the job reaches `completed`.

Completed output contains:

- `summary`
- `key_points`
- `topics`

## Learning Materials API

Learning Materials is independent of Quick Summary and video editing.

Create:

`POST /api/v1/learning-materials`

```json
{
  "video_id": "VIDEO_ID",
  "notes_style": "standard",
  "include_mind_map": true,
  "include_flowchart": true
}
```

Supported `notes_style` values are:

- `standard`
- `crisp`
- `high_yield`

Clients should send a unique `Idempotency-Key` header when creating a job.

Status:

`GET /api/v1/learning-materials/{learning_material_id}`

JSON result:

`GET /api/v1/learning-materials/{learning_material_id}/result`

PDF:

`GET /api/v1/learning-materials/{learning_material_id}/pdf`

The JSON result contains Notes, Mind Map, Flow Chart, `component_status`, and `component_errors`. A job may be `partial` when an optional visual component fails; the enterprise E2E gate requires all requested components to complete successfully.

## Video-editing APIs

The editing-summary workflow remains under:

`/api/v1/summaries`

Selections remain under:

`/api/v1/selections`

Rendering remains under:

`/api/v1/renders`

Intro/outro assets remain under:

`/api/v1/render-assets`

Quick Summary must not be implemented by repurposing `/api/v1/summaries`.

## Asynchronous processing

Quick Summary:

`API -> PostgreSQL job/outbox -> Quick Summary SQS -> dedicated worker -> persisted result`

Learning Materials:

`API -> PostgreSQL job/outbox -> Learning Materials SQS -> dedicated worker -> persisted result`

Rendering:

`API -> render job -> render SQS -> FFmpeg worker -> S3 output`

Clients create jobs and poll their status/result endpoints. They do not keep the initial generation or render request open while background processing runs.

## Authentication and tenant isolation

Production requests use Bearer JWT/OIDC authentication.

Tenant identity is derived by DT-FlashCut from the authenticated principal. Integrating clients must not send a trusted tenant identifier in the request body.

S3 access is restricted by the configured source bucket/prefix policy and IAM permissions. Cross-account source access, when required, must be configured through IAM/bucket policy and KMS permissions rather than public URLs.

## Idempotency

Create operations that support `Idempotency-Key` must be retried with the same request body and the same key.

A replay of the same request returns the original resource. Reusing the same key for a materially different request is invalid and should be treated as a conflict.

## Error handling

Integrating clients should treat:

- `401` as authentication failure.
- `403` as source or authorization policy rejection.
- `404` as missing source/resource.
- `409` as a state or idempotency conflict, including results requested before completion.
- `429` as rate limiting.
- `503` as temporary readiness/dependency failure.

Background-job failures are reported through the job status and error fields. Clients should not infer success only from the original `202` response.

## Handoff verification

Local or authenticated staging environments run the standard production gate:

```sh
./scripts/production-grade-test.sh
```

Generation-specific E2E verification runs:

```sh
./scripts/generation-e2e-test.sh
```

The generation gate validates:

- API readiness.
- editing-summary / Quick Summary / Learning Materials route separation.
- S3 source resolution.
- Quick Summary creation and idempotent replay.
- Learning Materials creation and idempotent replay.
- independent asynchronous worker completion.
- populated Quick Summary result.
- populated Notes, Mind Map, and Flow Chart.
- valid Learning Materials PDF.

For authenticated staging, supply the required environment-specific base URL, bearer token, source bucket, and source object key through environment variables. Do not commit those values.
