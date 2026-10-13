# DT-FlashCut API

Production REST API for DT-FlashCut.

The API is independently deployable and can be consumed without the DT-FlashCut web application.

## Local API

Base URL:

http://127.0.0.1:5002

OpenAPI:

http://127.0.0.1:5002/docs

## Main resources

- Videos
- Transcriptions
- Transcripts
- Automatic summaries
- Review selections
- Render jobs

## Asynchronous operations

Transcription, automatic summary generation and video rendering use job-based workflows.

## Security model

Clients use opaque IDs.

Raw S3 keys, AWS Transcribe job names and arbitrary render timestamps are not part of the public API contract.

## Production architecture

- FastAPI
- PostgreSQL
- Amazon S3
- Amazon Transcribe
- Amazon Bedrock
- Amazon SQS
- FFmpeg render worker
- ECS/Fargate target deployment
