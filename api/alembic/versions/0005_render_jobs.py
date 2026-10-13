"""render jobs

Revision ID: 0005
Revises: 0004
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "render_jobs",

        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "video_id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "selection_id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "source_etag",
            sa.String(length=256),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),

        sa.Column(
            "render_profile_version",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "output_filename",
            sa.String(length=512),
            nullable=True,
        ),

        sa.Column(
            "output_key",
            sa.String(length=2048),
            nullable=True,
        ),

        sa.Column(
            "output_size_bytes",
            sa.BigInteger(),
            nullable=True,
        ),

        sa.Column(
            "container_format",
            sa.String(length=16),
            nullable=True,
        ),

        sa.Column(
            "selected_seconds",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "error_code",
            sa.String(length=128),
            nullable=True,
        ),

        sa.Column(
            "error_message",
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
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["selection_id"],
            ["selections.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),
    )

    op.create_index(
        "ix_render_jobs_video_id",
        "render_jobs",
        ["video_id"],
    )

    op.create_index(
        "ix_render_jobs_selection_id",
        "render_jobs",
        ["selection_id"],
    )

    op.create_index(
        "ix_render_jobs_status",
        "render_jobs",
        ["status"],
    )

    op.create_index(
        "uq_render_jobs_reusable",
        "render_jobs",
        [
            "selection_id",
            "render_profile_version",
        ],
        unique=True,
        postgresql_where=sa.text(
            "status IN "
            "('queued','processing','completed')"
        ),
    )


def downgrade():
    op.drop_index(
        "uq_render_jobs_reusable",
        table_name="render_jobs",
    )

    op.drop_index(
        "ix_render_jobs_status",
        table_name="render_jobs",
    )

    op.drop_index(
        "ix_render_jobs_selection_id",
        table_name="render_jobs",
    )

    op.drop_index(
        "ix_render_jobs_video_id",
        table_name="render_jobs",
    )

    op.drop_table(
        "render_jobs"
    )
