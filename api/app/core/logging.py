import json
import logging
import sys
import traceback
from datetime import (
    datetime,
    timezone,
)


STRUCTURED_FIELDS = (
    "event",
    "request_id",
    "tenant_id",
    "subject",
    "method",
    "route",
    "path",
    "status_code",
    "duration_ms",
    "action",
    "outcome",
    "resource_type",
    "resource_id",
    "error_code",
    "job_id",
    "attempt_count",
)


class JsonFormatter(
    logging.Formatter
):
    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        payload = {
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "level":
                record.levelname,

            "logger":
                record.name,

            "message":
                record.getMessage(),
        }

        for field in STRUCTURED_FIELDS:
            value = getattr(
                record,
                field,
                None,
            )

            if value is not None:
                payload[
                    field
                ] = value

        if record.exc_info:
            payload[
                "exception"
            ] = "".join(
                traceback.format_exception(
                    *record.exc_info
                )
            ).strip()

        return json.dumps(
            payload,
            ensure_ascii=False,
        )


def configure_logging():
    root = logging.getLogger()

    root.handlers.clear()

    handler = logging.StreamHandler(
        sys.stdout
    )

    handler.setFormatter(
        JsonFormatter()
    )

    root.addHandler(
        handler
    )

    root.setLevel(
        logging.INFO
    )
