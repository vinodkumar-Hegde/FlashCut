import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.selection import Selection
from app.repositories.selection_repository import (
    SelectionRepository,
)
from app.repositories.summary_repository import (
    SummaryRepository,
)
from app.repositories.transcription_repository import (
    TranscriptionRepository,
)
from app.repositories.video_repository import (
    VideoRepository,
)


WORD_PADDING_SECONDS = 0.25


def utcnow():
    return datetime.now(
        timezone.utc
    )


class SelectionService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

        self.repo = SelectionRepository(
            db
        )

        self.summary_repo = SummaryRepository(
            db
        )

        self.transcript_repo = (
            TranscriptionRepository(
                db
            )
        )

        self.video_repo = VideoRepository(
            db
        )

    def _require_draft(
        self,
        selection: Selection,
    ):
        if selection.status != "draft":
            raise AppError(
                409,
                "SELECTION_IMMUTABLE",
                (
                    "An approved selection "
                    "cannot be modified."
                ),
            )

    def _resolve(
        self,
        *,
        transcript,
        segment_ids: list[int],
        word_ranges: list[dict],
    ) -> list[dict]:
        segment_map = {
            int(segment["id"]):
                segment
            for segment in transcript.segments
        }

        word_map = {
            int(word["id"]):
                word
            for word in transcript.words
        }

        intervals = []

        for segment_id in sorted(
            set(segment_ids)
        ):
            segment = segment_map.get(
                segment_id
            )

            if segment is None:
                raise AppError(
                    400,
                    "INVALID_SEGMENT_ID",
                    (
                        f"Transcript segment "
                        f"{segment_id} does not exist."
                    ),
                )

            intervals.append({
                "start":
                    float(segment["start"]),

                "end":
                    float(segment["end"]),

                "start_word_id":
                    segment.get(
                        "start_word_id"
                    ),

                "end_word_id":
                    segment.get(
                        "end_word_id"
                    ),

                "segment_ids":
                    [segment_id],

                "word_ranges":
                    [],

                "text":
                    segment.get(
                        "text",
                        "",
                    ),
            })

        for item in word_ranges:
            start_id = int(
                item["start_word_id"]
            )

            end_id = int(
                item["end_word_id"]
            )

            if start_id > end_id:
                raise AppError(
                    400,
                    "INVALID_WORD_RANGE",
                    (
                        "start_word_id must be "
                        "less than or equal to "
                        "end_word_id."
                    ),
                )

            start_word = word_map.get(
                start_id
            )

            end_word = word_map.get(
                end_id
            )

            if (
                start_word is None
                or end_word is None
            ):
                raise AppError(
                    400,
                    "INVALID_WORD_RANGE",
                    (
                        "One or more selected "
                        "word IDs do not exist."
                    ),
                )

            selected_words = [
                word_map[word_id]
                for word_id in range(
                    start_id,
                    end_id + 1,
                )
                if word_id in word_map
            ]

            intervals.append({
                "start":
                    max(
                        0.0,
                        float(
                            start_word["start"]
                        )
                        - WORD_PADDING_SECONDS,
                    ),

                "end":
                    float(
                        end_word["end"]
                    )
                    + WORD_PADDING_SECONDS,

                "start_word_id":
                    start_id,

                "end_word_id":
                    end_id,

                "segment_ids":
                    [],

                "word_ranges": [
                    {
                        "start_word_id":
                            start_id,

                        "end_word_id":
                            end_id,
                    }
                ],

                "text":
                    " ".join(
                        str(
                            word.get(
                                "text",
                                "",
                            )
                        )
                        for word
                        in selected_words
                    ).strip(),
            })

        if not intervals:
            return []

        intervals.sort(
            key=lambda item: (
                item["start"],
                item["end"],
            )
        )

        merged = []

        for interval in intervals:
            if not merged:
                merged.append(
                    interval
                )
                continue

            previous = merged[-1]

            if (
                interval["start"]
                <= previous["end"] + 0.05
            ):
                previous["end"] = max(
                    previous["end"],
                    interval["end"],
                )

                starts = [
                    value
                    for value in (
                        previous.get(
                            "start_word_id"
                        ),
                        interval.get(
                            "start_word_id"
                        ),
                    )
                    if value is not None
                ]

                ends = [
                    value
                    for value in (
                        previous.get(
                            "end_word_id"
                        ),
                        interval.get(
                            "end_word_id"
                        ),
                    )
                    if value is not None
                ]

                previous[
                    "start_word_id"
                ] = (
                    min(starts)
                    if starts
                    else None
                )

                previous[
                    "end_word_id"
                ] = (
                    max(ends)
                    if ends
                    else None
                )

                previous[
                    "segment_ids"
                ] = sorted(
                    set(
                        previous[
                            "segment_ids"
                        ]
                        + interval[
                            "segment_ids"
                        ]
                    )
                )

                previous[
                    "word_ranges"
                ].extend(
                    interval[
                        "word_ranges"
                    ]
                )

                if interval["text"]:
                    previous["text"] = (
                        (
                            previous["text"]
                            + " "
                            + interval["text"]
                        )
                        .strip()
                    )

            else:
                merged.append(
                    interval
                )

        resolved = []

        for index, clip in enumerate(
            merged,
            start=1,
        ):
            resolved.append({
                "clip_id":
                    index,

                "start":
                    round(
                        clip["start"],
                        3,
                    ),

                "end":
                    round(
                        clip["end"],
                        3,
                    ),

                "duration":
                    round(
                        clip["end"]
                        - clip["start"],
                        3,
                    ),

                "start_word_id":
                    clip[
                        "start_word_id"
                    ],

                "end_word_id":
                    clip[
                        "end_word_id"
                    ],

                "segment_ids":
                    clip[
                        "segment_ids"
                    ],

                "word_ranges":
                    clip[
                        "word_ranges"
                    ],

                "text":
                    clip["text"],
            })

        return resolved

    def create(
        self,
        *,
        video_id: str,
        summary_id: str | None,
    ) -> Selection:
        video = self.video_repo.get(
            video_id
        )

        if video is None:
            raise AppError(
                404,
                "VIDEO_NOT_FOUND",
                "Video not found.",
            )

        transcript = (
            self.transcript_repo
            .get_transcript(
                video_id
            )
        )

        if transcript is None:
            raise AppError(
                409,
                "TRANSCRIPT_REQUIRED",
                (
                    "The video must have a "
                    "transcript before creating "
                    "a selection."
                ),
            )

        if (
            video.etag
            and video.etag
            != transcript.source_etag
        ):
            raise AppError(
                409,
                "TRANSCRIPT_STALE",
                (
                    "The transcript no longer "
                    "matches the source video."
                ),
            )

        segment_ids = []

        if summary_id is not None:
            summary = (
                self.summary_repo.get(
                    summary_id
                )
            )

            if summary is None:
                raise AppError(
                    404,
                    "SUMMARY_NOT_FOUND",
                    "Summary not found.",
                )

            if summary.status != "completed":
                raise AppError(
                    409,
                    "SUMMARY_NOT_READY",
                    (
                        "The summary must be "
                        "completed first."
                    ),
                )

            if (
                summary.video_id
                != video_id
                or summary.transcript_id
                != transcript.id
            ):
                raise AppError(
                    400,
                    "SUMMARY_VIDEO_MISMATCH",
                    (
                        "The summary does not "
                        "belong to this video."
                    ),
                )

            segment_ids = [
                int(item["id"])
                for item
                in (
                    summary.selected_segments
                    or []
                )
            ]

        resolved = self._resolve(
            transcript=transcript,
            segment_ids=segment_ids,
            word_ranges=[],
        )

        selection = Selection(
            id=str(uuid.uuid4()),
            video_id=video_id,
            transcript_id=transcript.id,
            summary_id=summary_id,
            source_etag=(
                transcript.source_etag
            ),
            status="draft",
            revision=1,
            selected_segment_ids=(
                segment_ids
            ),
            word_ranges=[],
            resolved_clips=resolved,
        )

        self.db.add(
            selection
        )

        self.db.commit()

        self.db.refresh(
            selection
        )

        return selection

    def get(
        self,
        selection_id: str,
    ) -> Selection:
        selection = self.repo.get(
            selection_id
        )

        if selection is None:
            raise AppError(
                404,
                "SELECTION_NOT_FOUND",
                "Selection not found.",
            )

        return selection

    def update(
        self,
        *,
        selection_id: str,
        expected_revision: int,
        segment_ids: list[int],
        word_ranges: list[dict],
    ) -> Selection:
        selection = self.get(
            selection_id
        )

        self._require_draft(
            selection
        )

        if (
            selection.revision
            != expected_revision
        ):
            raise AppError(
                409,
                "SELECTION_REVISION_CONFLICT",
                (
                    "The selection was modified "
                    "by another request. Reload "
                    "it and retry."
                ),
            )

        transcript = (
            self.transcript_repo
            .get_transcript(
                selection.video_id
            )
        )

        if (
            transcript is None
            or transcript.id
            != selection.transcript_id
            or transcript.source_etag
            != selection.source_etag
        ):
            raise AppError(
                409,
                "TRANSCRIPT_CHANGED",
                (
                    "The underlying transcript "
                    "changed. Create a new "
                    "selection."
                ),
            )

        normalized_ranges = [
            {
                "start_word_id":
                    int(
                        item[
                            "start_word_id"
                        ]
                    ),

                "end_word_id":
                    int(
                        item[
                            "end_word_id"
                        ]
                    ),
            }
            for item in word_ranges
        ]

        resolved = self._resolve(
            transcript=transcript,
            segment_ids=segment_ids,
            word_ranges=(
                normalized_ranges
            ),
        )

        selection.selected_segment_ids = (
            sorted(
                set(segment_ids)
            )
        )

        selection.word_ranges = (
            normalized_ranges
        )

        selection.resolved_clips = (
            resolved
        )

        selection.revision += 1

        self.db.commit()

        self.db.refresh(
            selection
        )

        return selection

    def approve(
        self,
        *,
        selection_id: str,
        expected_revision: int,
    ) -> Selection:
        selection = self.get(
            selection_id
        )

        self._require_draft(
            selection
        )

        if (
            selection.revision
            != expected_revision
        ):
            raise AppError(
                409,
                "SELECTION_REVISION_CONFLICT",
                (
                    "Reload the selection "
                    "before approving it."
                ),
            )

        if not selection.resolved_clips:
            raise AppError(
                400,
                "EMPTY_SELECTION",
                (
                    "At least one clip must be "
                    "selected before approval."
                ),
            )

        selection.status = "approved"
        selection.approved_at = utcnow()
        selection.revision += 1

        self.db.commit()

        self.db.refresh(
            selection
        )

        return selection
