import logging

from app.core.config import (
    get_settings,
)
from app.core.logging import (
    configure_logging,
)
from app.repositories.generation_repository import (
    LearningMaterialRepository,
)
from app.services.learning_material_service import (
    LearningMaterialService,
)
from app.workers.generation_queue_worker import (
    run_worker,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.learning_material_worker"
)

settings = get_settings()


if __name__ == "__main__":
    run_worker(
        name="Learning material",

        logger=logger,

        queue_url=(
            settings
            .learning_material_queue_url
        ),

        message_key=(
            "learning_material_id"
        ),

        repo_class=(
            LearningMaterialRepository
        ),

        service_class=(
            LearningMaterialService
        ),
    )
