import logging

from app.core.config import (
    get_settings,
)
from app.core.logging import (
    configure_logging,
)
from app.repositories.generation_repository import (
    QuickSummaryRepository,
)
from app.services.quick_summary_service import (
    QuickSummaryService,
)
from app.workers.generation_queue_worker import (
    run_worker,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.quick_summary_worker"
)

settings = get_settings()


if __name__ == "__main__":
    run_worker(
        name="Quick summary",

        logger=logger,

        queue_url=(
            settings
            .quick_summary_queue_url
        ),

        message_key=(
            "quick_summary_id"
        ),

        repo_class=(
            QuickSummaryRepository
        ),

        service_class=(
            QuickSummaryService
        ),
    )
