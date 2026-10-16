"""intro and outro render assets

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "render_assets",

        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "tenant_id",
            sa.String(length=128),
            nullable=False,
        ),

        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
        ),

        sa.Column(
            "filename",
            sa.String(length=512),
            nullable=False,
        ),

        sa.Column(
            "s3_key",
            sa.String(length=2048),
            nullable=False,
        ),

        sa.Column(
            "content_type",
            sa.String(length=128),
            nullable=False,
        ),

        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "etag",
            sa.String(length=256),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(length=32),
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
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),

        sa.UniqueConstraint(
            "s3_key",
            name="uq_render_assets_s3_key",
        ),

        sa.CheckConstraint(
            "kind IN ('intro','outro')",
            name="ck_render_assets_kind",
        ),

        sa.CheckConstraint(
            "status IN "
            "('uploading','ready','rejected')",
            name="ck_render_assets_status",
        ),
    )

    op.create_index(
        "ix_render_assets_tenant_id",
        "render_assets",
        ["tenant_id"],
    )

    op.create_index(
        "ix_render_assets_status",
        "render_assets",
        ["status"],
    )

    op.create_index(
        "ix_render_assets_tenant_kind",
        "render_assets",
        [
            "tenant_id",
            "kind",
            "status",
        ],
    )

    op.add_column(
        "render_jobs",
        sa.Column(
            "intro_asset_id",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "render_jobs",
        sa.Column(
            "intro_asset_etag",
            sa.String(length=256),
            nullable=True,
        ),
    )

    op.add_column(
        "render_jobs",
        sa.Column(
            "outro_asset_id",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "render_jobs",
        sa.Column(
            "outro_asset_etag",
            sa.String(length=256),
            nullable=True,
        ),
    )

    op.add_column(
        "render_jobs",
        sa.Column(
            "render_fingerprint",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_render_jobs_intro_asset",
        "render_jobs",
        "render_assets",
        ["intro_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_foreign_key(
        "fk_render_jobs_outro_asset",
        "render_jobs",
        "render_assets",
        ["outro_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_render_jobs_intro_asset_id",
        "render_jobs",
        ["intro_asset_id"],
    )

    op.create_index(
        "ix_render_jobs_outro_asset_id",
        "render_jobs",
        ["outro_asset_id"],
    )

    op.drop_index(
        "uq_render_jobs_reusable",
        table_name="render_jobs",
    )

    op.create_index(
        "uq_render_jobs_reusable_fingerprint",
        "render_jobs",
        ["render_fingerprint"],
        unique=True,
        postgresql_where=sa.text(
            "render_fingerprint IS NOT NULL "
            "AND status IN "
            "('queued','processing','completed')"
        ),
    )


def downgrade():
    op.drop_index(
        "uq_render_jobs_reusable_fingerprint",
        table_name="render_jobs",
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

    op.drop_index(
        "ix_render_jobs_outro_asset_id",
        table_name="render_jobs",
    )

    op.drop_index(
        "ix_render_jobs_intro_asset_id",
        table_name="render_jobs",
    )

    op.drop_constraint(
        "fk_render_jobs_outro_asset",
        "render_jobs",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_render_jobs_intro_asset",
        "render_jobs",
        type_="foreignkey",
    )

    op.drop_column(
        "render_jobs",
        "render_fingerprint",
    )

    op.drop_column(
        "render_jobs",
        "outro_asset_etag",
    )

    op.drop_column(
        "render_jobs",
        "outro_asset_id",
    )

    op.drop_column(
        "render_jobs",
        "intro_asset_etag",
    )

    op.drop_column(
        "render_jobs",
        "intro_asset_id",
    )

    op.drop_index(
        "ix_render_assets_tenant_kind",
        table_name="render_assets",
    )

    op.drop_index(
        "ix_render_assets_status",
        table_name="render_assets",
    )

    op.drop_index(
        "ix_render_assets_tenant_id",
        table_name="render_assets",
    )

    op.drop_table(
        "render_assets"
    )
