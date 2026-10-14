from app.db.session import (
    SessionLocal,
)
from app.models.audit import (
    AuditEvent,
)


def write_audit_event(
    *,
    tenant_id: str | None,
    actor_subject: str | None,
    request_id: str,
    method: str,
    route: str | None,
    path: str,
    status_code: int,
    action: str,
    outcome: str,
    resource_type: str | None,
    resource_id: str | None,
    duration_ms: float,
    error_code: str | None,
    details: dict,
) -> None:
    with SessionLocal() as db:
        event = AuditEvent(
            tenant_id=tenant_id,
            actor_subject=(
                actor_subject
            ),
            request_id=request_id,
            method=method,
            route=route,
            path=path,
            status_code=status_code,
            action=action,
            outcome=outcome,
            resource_type=(
                resource_type
            ),
            resource_id=(
                resource_id
            ),
            duration_ms=(
                duration_ms
            ),
            error_code=error_code,
            details=details,
        )

        db.add(event)
        db.commit()
