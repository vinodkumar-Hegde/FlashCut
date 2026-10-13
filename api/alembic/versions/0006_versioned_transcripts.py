"""immutable versioned transcripts

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "transcription_jobs",
        sa.Column(
            "language_code",
            sa.String(length=32),
            nullable=True,
        ),
    )

    op.add_column(
        "transcription_jobs",
        sa.Column(
            "vocabulary_name",
            sa.String(length=256),
            nullable=False,
            server_default="",
        ),
    )

    op.add_column(
        "transcription_jobs",
        sa.Column(
            "config_version",
            sa.String(length=64),
            nullable=False,
            server_default="v1",
        ),
    )

    op.execute(
        """
        UPDATE transcription_jobs AS j
        SET language_code = COALESCE(
            (
                SELECT t.language_code
                FROM transcripts AS t
                WHERE
                    t.video_id = j.video_id
                    AND t.source_etag = j.source_etag
                ORDER BY t.created_at DESC
                LIMIT 1
            ),
            'en-US'
        )
        WHERE j.language_code IS NULL
        """
    )

    op.alter_column(
        "transcription_jobs",
        "language_code",
        nullable=False,
    )

    op.drop_index(
        "uq_transcription_jobs_active",
        table_name="transcription_jobs",
    )

    op.create_index(
        "uq_transcription_jobs_active_v2",
        "transcription_jobs",
        [
            "video_id",
            "source_etag",
            "language_code",
            "vocabulary_name",
            "config_version",
        ],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'in_progress')"
        ),
    )

    op.add_column(
        "transcripts",
        sa.Column(
            "transcription_job_id",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "transcripts",
        sa.Column(
            "vocabulary_name",
            sa.String(length=256),
            nullable=False,
            server_default="",
        ),
    )

    op.add_column(
        "transcripts",
        sa.Column(
            "config_version",
            sa.String(length=64),
            nullable=False,
            server_default="v1",
        ),
    )

    op.execute(
        """
        UPDATE transcripts
        SET language_code = 'en-US'
        WHERE language_code IS NULL
        """
    )

    op.alter_column(
        "transcripts",
        "language_code",
        nullable=False,
    )

    op.execute(
        """
        UPDATE transcripts AS t
        SET transcription_job_id = (
            SELECT j.id
            FROM transcription_jobs AS j
            WHERE
                j.video_id = t.video_id
                AND j.source_etag = t.source_etag
                AND j.status = 'completed'
            ORDER BY
                j.completed_at DESC NULLS LAST,
                j.created_at DESC
            LIMIT 1
        )
        WHERE t.transcription_job_id IS NULL
        """
    )

    op.create_foreign_key(
        "fk_transcripts_transcription_job_id",
        "transcripts",
        "transcription_jobs",
        ["transcription_job_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_index(
        "ix_transcripts_video_id",
        table_name="transcripts",
    )

    op.drop_constraint(
        "transcripts_video_id_key",
        "transcripts",
        type_="unique",
    )

    op.create_index(
        "ix_transcripts_video_id",
        "transcripts",
        ["video_id"],
        unique=False,
    )

    op.create_index(
        "uq_transcripts_transcription_job_id",
        "transcripts",
        ["transcription_job_id"],
        unique=True,
        postgresql_where=sa.text(
            "transcription_job_id IS NOT NULL"
        ),
    )

    op.create_index(
        "ix_transcripts_cache_lookup",
        "transcripts",
        [
            "video_id",
            "source_etag",
            "language_code",
            "vocabulary_name",
            "config_version",
            "created_at",
        ],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_transcripts_cache_lookup",
        table_name="transcripts",
    )

    op.drop_index(
        "uq_transcripts_transcription_job_id",
        table_name="transcripts",
    )

    op.drop_constraint(
        "fk_transcripts_transcription_job_id",
        "transcripts",
        type_="foreignkey",
    )

    op.drop_column(
        "transcripts",
        "config_version",
    )

    op.drop_column(
        "transcripts",
        "vocabulary_name",
    )

    op.drop_column(
        "transcripts",
        "transcription_job_id",
    )

    op.drop_index(
        "uq_transcription_jobs_active_v2",
        table_name="transcription_jobs",
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

    op.drop_column(
        "transcription_jobs",
        "config_version",
    )

    op.drop_column(
        "transcription_jobs",
        "vocabulary_name",
    )

    op.drop_column(
        "transcription_jobs",
        "language_code",
    )
