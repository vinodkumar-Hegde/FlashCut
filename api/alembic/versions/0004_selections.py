"""review selections

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "selections",

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
            "summary_id",
            sa.String(length=36),
            nullable=True,
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
            "revision",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "selected_segment_ids",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "word_ranges",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "resolved_clips",
            postgresql.JSONB(),
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

        sa.Column(
            "approved_at",
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
            ["summary_id"],
            ["summary_jobs.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_selections_video_id",
        "selections",
        ["video_id"],
    )

    op.create_index(
        "ix_selections_transcript_id",
        "selections",
        ["transcript_id"],
    )

    op.create_index(
        "ix_selections_summary_id",
        "selections",
        ["summary_id"],
    )

    op.create_index(
        "ix_selections_status",
        "selections",
        ["status"],
    )


def downgrade():
    op.drop_index(
        "ix_selections_status",
        table_name="selections",
    )

    op.drop_index(
        "ix_selections_summary_id",
        table_name="selections",
    )

    op.drop_index(
        "ix_selections_transcript_id",
        table_name="selections",
    )

    op.drop_index(
        "ix_selections_video_id",
        table_name="selections",
    )

    op.drop_table("selections")
