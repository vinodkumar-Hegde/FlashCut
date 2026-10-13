from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    Principal,
    require_principal,
)
from app.db.session import get_db
from app.schemas.videos import (
    RenameVideoRequest,
    VideoListResponse,
    VideoResponse,
)
from app.services.video_service import (
    VideoService,
)


router = APIRouter(
    prefix="/api/v1/videos",
    tags=["videos"],
)


def to_response(
    video,
) -> VideoResponse:
    return VideoResponse(
        id=video.id,
        name=video.filename,
        etag=video.etag,
        updated_at=video.updated_at,
    )


@router.get(
    "",
    response_model=VideoListResponse,
)
def list_videos(
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    service = VideoService(
        db
    )

    videos = (
        service.sync_from_s3()
    )

    items = [
        to_response(
            video
        )
        for video in videos
    ]

    return VideoListResponse(
        items=items,
        count=len(items),
    )


@router.post(
    "/{video_id}/rename",
    response_model=VideoResponse,
)
def rename_video(
    video_id: str,
    body: RenameVideoRequest,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    service = VideoService(
        db
    )

    video = service.rename(
        video_id=video_id,
        new_name=body.new_name,
    )

    return to_response(
        video
    )
