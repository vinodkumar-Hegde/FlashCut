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
from app.db.session import get_tenant_db
from app.schemas.render_assets import (
    CreateRenderAssetUploadRequest,
    RenderAssetPreviewResponse,
    RenderAssetResponse,
    RenderAssetUploadResponse,
)
from app.services.render_asset_service import (
    RenderAssetService,
)


router = APIRouter(
    prefix="/api/v1/render-assets",
    tags=["render-assets"],
)


def to_response(
    asset,
):
    return RenderAssetResponse(
        id=asset.id,
        kind=asset.kind,
        filename=asset.filename,
        content_type=(
            asset.content_type
        ),
        size_bytes=(
            asset.size_bytes
        ),
        status=asset.status,
        etag=asset.etag,
        created_at=(
            asset.created_at
        ),
        completed_at=(
            asset.completed_at
        ),
    )


@router.post(
    "/uploads",
    response_model=(
        RenderAssetUploadResponse
    ),
    status_code=201,
)
def create_upload(
    body: CreateRenderAssetUploadRequest,
    db: Annotated[
        Session,
        Depends(get_tenant_db),
    ],
    principal: Annotated[
        Principal,
        Depends(require_principal),
    ],
):
    _, response = (
        RenderAssetService(db)
        .create_upload(
            kind=body.kind,
            filename=body.filename,
            content_type=(
                body.content_type
            ),
            size_bytes=(
                body.size_bytes
            ),
        )
    )

    return response


@router.post(
    "/{asset_id}/complete",
    response_model=RenderAssetResponse,
)
def complete_upload(
    asset_id: str,
    db: Annotated[
        Session,
        Depends(get_tenant_db),
    ],
    principal: Annotated[
        Principal,
        Depends(require_principal),
    ],
):
    asset = (
        RenderAssetService(db)
        .complete(
            asset_id
        )
    )

    return to_response(
        asset
    )


@router.get(
    "/{asset_id}",
    response_model=RenderAssetResponse,
)
def get_asset(
    asset_id: str,
    db: Annotated[
        Session,
        Depends(get_tenant_db),
    ],
    principal: Annotated[
        Principal,
        Depends(require_principal),
    ],
):
    asset = (
        RenderAssetService(db)
        .get(
            asset_id
        )
    )

    return to_response(
        asset
    )


@router.get(
    "/{asset_id}/preview",
    response_model=(
        RenderAssetPreviewResponse
    ),
)
def preview_asset(
    asset_id: str,
    db: Annotated[
        Session,
        Depends(get_tenant_db),
    ],
    principal: Annotated[
        Principal,
        Depends(require_principal),
    ],
):
    return (
        RenderAssetService(db)
        .preview(
            asset_id
        )
    )
