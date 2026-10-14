"""idempotency keys

Revision ID: 0010
Revises: 0009
"""

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


TABLES = [
    "selections",
    "note_jobs",
]


def upgrade():
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "idempotency_key",
                sa.String(
                    length=128
                ),
                nullable=True,
            ),
        )

        op.add_column(
            table,
            sa.Column(
                "idempotency_hash",
                sa.String(
                    length=64
                ),
                nullable=True,
            ),
        )

        op.create_index(
            (
                f"uq_{table}_tenant_"
                "idempotency_key"
            ),
            table,
            [
                "tenant_id",
                "idempotency_key",
            ],
            unique=True,
            postgresql_where=(
                sa.text(
                    "idempotency_key "
                    "IS NOT NULL"
                )
            ),
        )


def downgrade():
    for table in reversed(
        TABLES
    ):
        op.drop_index(
            (
                f"uq_{table}_tenant_"
                "idempotency_key"
            ),
            table_name=table,
        )

        op.drop_column(
            table,
            "idempotency_hash",
        )

        op.drop_column(
            table,
            "idempotency_key",
        )
