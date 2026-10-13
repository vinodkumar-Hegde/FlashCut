"""create videos

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "videos",

        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "s3_key",
            sa.String(length=2048),
            nullable=False,
        ),

        sa.Column(
            "filename",
            sa.String(length=512),
            nullable=False,
        ),

        sa.Column(
            "etag",
            sa.String(length=256),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),

        sa.UniqueConstraint(
            "s3_key"
        ),
    )

    op.create_index(
        "ix_videos_s3_key",
        "videos",
        ["s3_key"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "ix_videos_s3_key",
        table_name="videos",
    )

    op.drop_table(
        "videos"
    )
