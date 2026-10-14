import logging
import time
from datetime import (
    datetime,
    timezone,
)

from app.core.logging import (
    configure_logging,
)
from app.db.session import SessionLocal
from app.repositories.note_repository import (
    NoteRepository,
)
from app.services.note_service import (
    NoteService,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.notes_worker"
)


def utcnow():
    return datetime.now(
        timezone.utc
    )


def run():
    logger.info(
        "Notes worker started"
    )

    while True:
        with SessionLocal() as db:
            job = (
                NoteRepository(db)
                .claim_next(
                    now=utcnow()
                )
            )

            if job is None:
                time.sleep(2)
                continue

            note_id = job.id

        logger.info(
            "Processing notes %s",
            note_id,
        )

        with SessionLocal() as db:
            try:
                NoteService(
                    db
                ).process(
                    note_id
                )

            except Exception:
                logger.exception(
                    "Notes failed: %s",
                    note_id,
                )

                db.rollback()

                repo = NoteRepository(
                    db
                )

                failed = repo.get(
                    note_id
                )

                if failed is not None:
                    failed.status = (
                        "failed"
                    )

                    failed.failure_reason = (
                        "Automatic notes "
                        "generation failed."
                    )

                    failed.completed_at = (
                        utcnow()
                    )

                    failed.next_attempt_at = (
                        None
                    )

                    db.commit()

            else:
                current = (
                    NoteRepository(db)
                    .get(
                        note_id
                    )
                )

                if (
                    current is not None
                    and current.status
                    == "completed"
                ):
                    logger.info(
                        "Notes completed: %s",
                        note_id,
                    )


if __name__ == "__main__":
    run()
