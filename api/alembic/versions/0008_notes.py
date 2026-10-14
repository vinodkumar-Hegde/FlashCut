"""automatic editable notes

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "note_jobs",

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
            nullable=True,
        ),

        sa.Column(
            "transcription_job_id",
            sa.String(length=36),
            nullable=True,
        ),

        sa.Column(
            "source_etag",
            sa.String(length=256),
            nullable=True,
        ),

        sa.Column(
            "style",
            sa.String(length=32),
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
            "content",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "visuals",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "failure_reason",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
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

        sa.ForeignKeyConstraint(
            ["transcription_job_id"],
            ["transcription_jobs.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_note_jobs_video_id",
        "note_jobs",
        ["video_id"],
    )

    op.create_index(
        "ix_note_jobs_transcript_id",
        "note_jobs",
        ["transcript_id"],
    )

    op.create_index(
        "ix_note_jobs_status",
        "note_jobs",
        ["status"],
    )

    op.create_index(
        "ix_note_jobs_claim",
        "note_jobs",
        [
            "status",
            "next_attempt_at",
            "created_at",
        ],
    )


def downgrade():
    op.drop_index(
        "ix_note_jobs_claim",
        table_name="note_jobs",
    )

    op.drop_index(
        "ix_note_jobs_status",
        table_name="note_jobs",
    )

    op.drop_index(
        "ix_note_jobs_transcript_id",
        table_name="note_jobs",
    )

    op.drop_index(
        "ix_note_jobs_video_id",
        table_name="note_jobs",
    )

    op.drop_table(
        "note_jobs"
    )
