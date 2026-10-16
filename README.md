# FlashCut

Product: DT-FlashCut

DT-FlashCut is a transcript-driven educational video editing platform.

## Repository structure

api/
Independent DT-FlashCut REST API and background workers.
It can be deployed and consumed without the DT-FlashCut web frontend.

web/
Independent DT-FlashCut browser application.
It communicates with the backend through the public /api/v1 contract.

## Production workflows

Video editing:
S3 video -> transcript -> editing summary -> approved selection
-> SQS render job -> FFmpeg worker -> generated S3 video.

Quick Summary:
video -> Quick Summary job -> transactional outbox
-> dedicated SQS queue -> dedicated worker -> result.

Learning Materials:
video -> Learning Materials job -> transactional outbox
-> dedicated SQS queue -> dedicated worker
-> Notes / Mind Map / Flow Chart / PDF.

## Source-video integration

Integrating systems map Course / Subject / Topic to an approved
S3 bucket and object key and call `/api/v1/videos/resolve`.
Downstream APIs use the returned DT-FlashCut `video_id`.
Arbitrary public or presigned URLs are not trusted render inputs.

## Integration and QA handoff

Detailed integration contract:
`docs/integration-api.md`

Generation E2E gate:
`./scripts/generation-e2e-test.sh`

## API-only local stack

docker compose -f docker-compose.api.yml up -d --build

API:
http://127.0.0.1:5002

OpenAPI:
http://127.0.0.1:5002/docs

## Product naming

Application: DT-FlashCut
API: DT-FlashCut API
Repository: FlashCut
