"""generation queue outboxes

Revision ID: 0014
Revises: 0013
"""

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def create_outbox(
    table_name: str,
    job_table: str,
):
    op.create_table(
        table_name,

        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),

        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey(
                f"{job_table}.id",
                ondelete="CASCADE",
            ),
            nullable=False,
            unique=True,
        ),

        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),

        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "next_attempt_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
            server_default=(
                sa.func.now()
            ),
        ),

        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
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

        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
            server_default=(
                sa.func.now()
            ),
        ),

        sa.Column(
            "sent_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),
    )

    op.create_index(
        (
            "ix_"
            + table_name
            + "_status_next"
        ),
        table_name,
        [
            "status",
            "next_attempt_at",
        ],
    )


def upgrade():
    create_outbox(
        "quick_summary_outbox",
        "quick_summary_jobs",
    )

    create_outbox(
        "learning_material_outbox",
        "learning_material_jobs",
    )


def downgrade():
    op.drop_index(
        "ix_learning_material_outbox_status_next",
        table_name=(
            "learning_material_outbox"
        ),
    )

    op.drop_table(
        "learning_material_outbox"
    )

    op.drop_index(
        "ix_quick_summary_outbox_status_next",
        table_name=(
            "quick_summary_outbox"
        ),
    )

    op.drop_table(
        "quick_summary_outbox"
    )
