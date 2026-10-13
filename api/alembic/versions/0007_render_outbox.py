"""reliable render outbox

Revision ID: 0007
Revises: 0006
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "render_outbox",

        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "render_id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),

        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["render_id"],
            ["render_jobs.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "render_id",
            name="uq_render_outbox_render_id",
        ),
    )

    op.create_index(
        "ix_render_outbox_pending",
        "render_outbox",
        [
            "status",
            "next_attempt_at",
        ],
    )


def downgrade():
    op.drop_index(
        "ix_render_outbox_pending",
        table_name="render_outbox",
    )

    op.drop_table(
        "render_outbox"
    )
