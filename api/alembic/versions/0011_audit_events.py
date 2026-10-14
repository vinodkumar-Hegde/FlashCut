"""audit events

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import (
    postgresql,
)


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_events",

        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),

        sa.Column(
            "tenant_id",
            sa.String(128),
            nullable=True,
        ),

        sa.Column(
            "actor_subject",
            sa.String(256),
            nullable=True,
        ),

        sa.Column(
            "request_id",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "method",
            sa.String(16),
            nullable=False,
        ),

        sa.Column(
            "route",
            sa.String(512),
            nullable=True,
        ),

        sa.Column(
            "path",
            sa.String(2048),
            nullable=False,
        ),

        sa.Column(
            "status_code",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "action",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "outcome",
            sa.String(32),
            nullable=False,
        ),

        sa.Column(
            "resource_type",
            sa.String(64),
            nullable=True,
        ),

        sa.Column(
            "resource_id",
            sa.String(128),
            nullable=True,
        ),

        sa.Column(
            "duration_ms",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "error_code",
            sa.String(128),
            nullable=True,
        ),

        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
            server_default=(
                sa.func.now()
            ),
        ),
    )

    op.create_index(
        "ix_audit_events_tenant_created_at",
        "audit_events",
        [
            "tenant_id",
            "created_at",
        ],
    )

    op.create_index(
        "ix_audit_events_request_id",
        "audit_events",
        [
            "request_id",
        ],
    )

    op.create_index(
        "ix_audit_events_resource",
        "audit_events",
        [
            "tenant_id",
            "resource_type",
            "resource_id",
        ],
    )


def downgrade():
    op.drop_index(
        "ix_audit_events_resource",
        table_name="audit_events",
    )

    op.drop_index(
        "ix_audit_events_request_id",
        table_name="audit_events",
    )

    op.drop_index(
        "ix_audit_events_tenant_created_at",
        table_name="audit_events",
    )

    op.drop_table(
        "audit_events"
    )
