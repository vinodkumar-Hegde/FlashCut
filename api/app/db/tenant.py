from sqlalchemy import select
from sqlalchemy.orm import Session


def current_tenant_id(
    db: Session,
) -> str | None:
    value = db.info.get(
        "tenant_id"
    )

    if value is None:
        return None

    return str(value)


def tenant_select(
    db: Session,
    model,
):
    statement = select(model)

    tenant_id = current_tenant_id(
        db
    )

    if tenant_id is not None:
        statement = statement.where(
            model.tenant_id
            == tenant_id
        )

    return statement


def tenant_get(
    db: Session,
    model,
    object_id: str,
):
    statement = (
        tenant_select(
            db,
            model,
        )
        .where(
            model.id
            == object_id
        )
        .limit(1)
    )

    return db.scalar(
        statement
    )
