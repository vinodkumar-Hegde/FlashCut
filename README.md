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

legacy/
Temporary copy of the original Flask prototype.
It is retained during migration only.

## Production workflow

S3 video
-> Amazon Transcribe
-> transcript
-> Automatic Summary
-> user review
-> approved selection
-> SQS render job
-> FFmpeg render worker
-> generated S3 video

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
