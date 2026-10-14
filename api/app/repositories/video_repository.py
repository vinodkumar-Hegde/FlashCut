from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
    tenant_select,
)
from app.models.video import Video


class VideoRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        video_id: str,
    ) -> Video | None:
        return tenant_get(
            self.db,
            Video,
            video_id,
        )

    def get_by_key(
        self,
        key: str,
    ) -> Video | None:
        statement = (
            tenant_select(
                self.db,
                Video,
            )
            .where(
                Video.s3_key
                == key
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def list_all(
        self,
    ) -> list[Video]:
        statement = (
            tenant_select(
                self.db,
                Video,
            )
            .order_by(
                Video.filename
            )
        )

        return list(
            self.db.scalars(
                statement
            )
        )

    def upsert(
        self,
        *,
        key: str,
        filename: str,
        etag: str | None,
    ) -> Video:
        video = self.get_by_key(
            key
        )

        if video is None:
            video = Video(
                s3_key=key,
                filename=filename,
                etag=etag,
            )

            self.db.add(
                video
            )

        else:
            video.filename = (
                filename
            )

            video.etag = etag

        return video
