from typing import Annotated

from fastapi import Depends
from sqlalchemy import (
    create_engine,
    event,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from app.core.auth import (
    Principal,
    require_principal,
)
from app.core.config import (
    get_settings,
)


settings = get_settings()


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


@event.listens_for(
    Session,
    "before_flush",
)
def assign_tenant_to_new_objects(
    session,
    flush_context,
    instances,
):
    tenant_id = session.info.get(
        "tenant_id"
    )

    if not tenant_id:
        return

    for item in session.new:
        if not hasattr(
            item,
            "tenant_id",
        ):
            continue

        if getattr(
            item,
            "tenant_id",
            None,
        ):
            continue

        item.tenant_id = str(
            tenant_id
        )


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_tenant_db(
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    db = SessionLocal()

    db.info[
        "tenant_id"
    ] = principal.tenant_id

    try:
        yield db
    finally:
        db.close()
