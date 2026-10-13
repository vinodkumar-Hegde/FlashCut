# DT-FlashCut Web

Independent browser application for DT-FlashCut.

The web application consumes the DT-FlashCut REST API.

Production API contract:

- GET /api/v1/videos
- POST /api/v1/transcriptions
- GET /api/v1/transcriptions/{job_id}
- GET /api/v1/videos/{video_id}/transcript
- GET /api/v1/videos/{video_id}/transcript/words
- POST /api/v1/summaries
- GET /api/v1/summaries/{summary_id}
- POST /api/v1/selections
- PUT /api/v1/selections/{selection_id}
- POST /api/v1/selections/{selection_id}/approve
- POST /api/v1/renders
- GET /api/v1/renders/{render_id}
- GET /api/v1/renders/{render_id}/result

The browser must never submit arbitrary timestamps for rendering.
Selections are represented using server-owned transcript segment and word IDs.
