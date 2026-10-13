from sqlalchemy.orm import Session

from app.models.selection import Selection


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
        return self.db.get(
            Selection,
            selection_id,
        )
