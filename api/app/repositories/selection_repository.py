from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
    tenant_select,
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

    def get_by_idempotency_key(
        self,
        key: str,
    ) -> Selection | None:
        statement = (
            tenant_select(
                self.db,
                Selection,
            )
            .where(
                Selection
                .idempotency_key
                == key
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )
