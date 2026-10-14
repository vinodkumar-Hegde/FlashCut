"""tenant ownership

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


TENANT_TABLES = [
    "videos",
    "transcription_jobs",
    "transcripts",
    "summary_jobs",
    "selections",
    "render_jobs",
    "note_jobs",
]


def upgrade():
    for table in TENANT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                sa.String(
                    length=128
                ),
                nullable=True,
                server_default=(
                    "local-development"
                ),
            ),
        )

        op.execute(
            f"""
            UPDATE {table}
            SET tenant_id =
                'local-development'
            WHERE tenant_id IS NULL
            """
        )

        op.alter_column(
            table,
            "tenant_id",
            existing_type=(
                sa.String(
                    length=128
                )
            ),
            nullable=False,
            server_default=None,
        )

        op.create_index(
            f"ix_{table}_tenant_id",
            table,
            ["tenant_id"],
        )

    op.execute(
        """
        ALTER TABLE videos
        DROP CONSTRAINT IF EXISTS
        videos_s3_key_key
        """
    )

    op.create_index(
        "uq_videos_tenant_s3_key",
        "videos",
        [
            "tenant_id",
            "s3_key",
        ],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "uq_videos_tenant_s3_key",
        table_name="videos",
    )

    op.create_unique_constraint(
        "videos_s3_key_key",
        "videos",
        ["s3_key"],
    )

    for table in reversed(
        TENANT_TABLES
    ):
        op.drop_index(
            f"ix_{table}_tenant_id",
            table_name=table,
        )

        op.drop_column(
            table,
            "tenant_id",
        )
