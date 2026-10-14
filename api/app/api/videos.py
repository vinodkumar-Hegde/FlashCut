from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    Principal,
    require_principal,
)
from app.db.session import (
    get_tenant_db,
)
from app.schemas.videos import (
    RenameVideoRequest,
    ResolveVideoRequest,
    ResolveVideoResponse,
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
        Depends(
            get_tenant_db
        ),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    videos = (
        VideoService(db)
        .list_for_api()
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
    "/resolve",
    response_model=(
        ResolveVideoResponse
    ),
    responses={
        200: {
            "description":
                "Existing tenant video "
                "resolved."
        },
        201: {
            "description":
                "New tenant video "
                "registered."
        },
        403: {
            "description":
                "Source location is not "
                "allowed."
        },
        404: {
            "description":
                "Source video was not "
                "found."
        },
        409: {
            "description":
                "Source ETag changed."
        },
    },
)
def resolve_video(
    body: ResolveVideoRequest,
    response: Response,
    db: Annotated[
        Session,
        Depends(
            get_tenant_db
        ),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    video, created = (
        VideoService(db)
        .resolve_source(
            bucket=body.bucket,
            key=body.key,
            expected_etag=(
                body.expected_etag
            ),
        )
    )

    response.status_code = (
        status.HTTP_201_CREATED
        if created
        else status.HTTP_200_OK
    )

    return ResolveVideoResponse(
        id=video.id,
        name=video.filename,
        etag=video.etag,
        updated_at=video.updated_at,
        created=created,
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
        Depends(
            get_tenant_db
        ),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    video = (
        VideoService(db)
        .rename(
            video_id=video_id,
            new_name=body.new_name,
        )
    )

    return to_response(
        video
    )
