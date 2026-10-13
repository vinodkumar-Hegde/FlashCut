"""automatic summary jobs

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "summary_jobs",

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
            "transcript_id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "source_etag",
            sa.String(length=256),
            nullable=False,
        ),

        sa.Column(
            "target_seconds",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),

        sa.Column(
            "model_id",
            sa.String(length=512),
            nullable=False,
        ),

        sa.Column(
            "algorithm_version",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "selected_segments",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "notes",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "coverage_topics",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "candidate_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "selected_seconds",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "budget_usage_pct",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "failure_reason",
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
            ["transcript_id"],
            ["transcripts.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),
    )

    op.create_index(
        "ix_summary_jobs_video_id",
        "summary_jobs",
        ["video_id"],
    )

    op.create_index(
        "ix_summary_jobs_transcript_id",
        "summary_jobs",
        ["transcript_id"],
    )

    op.create_index(
        "ix_summary_jobs_status",
        "summary_jobs",
        ["status"],
    )

    op.create_index(
        "uq_summary_jobs_active",
        "summary_jobs",
        [
            "transcript_id",
            "target_seconds",
            "model_id",
            "algorithm_version",
        ],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'processing')"
        ),
    )


def downgrade():
    op.drop_index(
        "uq_summary_jobs_active",
        table_name="summary_jobs",
    )

    op.drop_index(
        "ix_summary_jobs_status",
        table_name="summary_jobs",
    )

    op.drop_index(
        "ix_summary_jobs_transcript_id",
        table_name="summary_jobs",
    )

    op.drop_index(
        "ix_summary_jobs_video_id",
        table_name="summary_jobs",
    )

    op.drop_table(
        "summary_jobs"
    )
