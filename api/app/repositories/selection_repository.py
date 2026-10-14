from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
)
from app.models.selection import (
    Selection,
)


class SelectionRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        selection_id: str,
    ) -> Selection | None:
        return tenant_get(
            self.db,
            Selection,
            selection_id,
        )
