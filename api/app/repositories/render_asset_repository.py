from sqlalchemy.orm import Session

from app.db.tenant import tenant_get
from app.models.render_asset import (
    RenderAsset,
)


class RenderAssetRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        asset_id: str,
    ) -> RenderAsset | None:
        return tenant_get(
            self.db,
            RenderAsset,
            asset_id,
        )
