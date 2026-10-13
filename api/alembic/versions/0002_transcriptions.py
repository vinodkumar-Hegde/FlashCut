"""transcription jobs and transcripts

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transcription_jobs",

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
            "provider_job_name",
            sa.String(length=256),
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
            "output_key",
            sa.String(length=2048),
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

        sa.PrimaryKeyConstraint(
            "id"
        ),

        sa.UniqueConstraint(
            "provider_job_name"
        ),
    )

    op.create_index(
        "ix_transcription_jobs_video_id",
        "transcription_jobs",
        ["video_id"],
    )

    op.create_index(
        "ix_transcription_jobs_status",
        "transcription_jobs",
        ["status"],
    )

    op.create_index(
        "uq_transcription_jobs_active",
        "transcription_jobs",
        [
            "video_id",
            "source_etag",
        ],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'in_progress')"
        ),
    )

    op.create_table(
        "transcripts",

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
            "source_etag",
            sa.String(length=256),
            nullable=False,
        ),

        sa.Column(
            "language_code",
            sa.String(length=32),
            nullable=True,
        ),

        sa.Column(
            "full_text",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "segments",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
        ),

        sa.Column(
            "words",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
        ),

        sa.Column(
            "raw_output_key",
            sa.String(length=2048),
            nullable=False,
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

        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),

        sa.UniqueConstraint(
            "video_id"
        ),
    )

    op.create_index(
        "ix_transcripts_video_id",
        "transcripts",
        ["video_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "ix_transcripts_video_id",
        table_name="transcripts",
    )

    op.drop_table(
        "transcripts"
    )

    op.drop_index(
        "uq_transcription_jobs_active",
        table_name="transcription_jobs",
    )

    op.drop_index(
        "ix_transcription_jobs_status",
        table_name="transcription_jobs",
    )

    op.drop_index(
        "ix_transcription_jobs_video_id",
        table_name="transcription_jobs",
    )

    op.drop_table(
        "transcription_jobs"
    )
