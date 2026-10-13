from sqlalchemy import select
from sqlalchemy.orm import Session

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
        return self.db.get(
            Video,
            video_id,
        )

    def get_by_key(
        self,
        key: str,
    ) -> Video | None:
        statement = select(
            Video
        ).where(
            Video.s3_key == key
        )

        return self.db.scalar(
            statement
        )

    def list_all(
        self,
    ) -> list[Video]:
        statement = (
            select(Video)
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
            video.filename = filename
            video.etag = etag

        return video
