"""quick summaries and learning materials

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quick_summary_jobs",

        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),

        sa.Column(
            "tenant_id",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "idempotency_key",
            sa.String(128),
            nullable=True,
        ),

        sa.Column(
            "idempotency_hash",
            sa.String(64),
            nullable=True,
        ),

        sa.Column(
            "video_id",
            sa.String(36),
            sa.ForeignKey(
                "videos.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "transcript_id",
            sa.String(36),
            sa.ForeignKey(
                "transcripts.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),

        sa.Column(
            "transcription_job_id",
            sa.String(36),
            sa.ForeignKey(
                "transcription_jobs.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),

        sa.Column(
            "source_etag",
            sa.String(256),
            nullable=True,
        ),

        sa.Column(
            "fingerprint",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
        ),

        sa.Column(
            "model_id",
            sa.String(512),
            nullable=False,
        ),

        sa.Column(
            "algorithm_version",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "result",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "error_code",
            sa.String(128),
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
            server_default=sa.func.now(),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
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
    )

    op.create_index(
        "ix_quick_summary_jobs_tenant_created",
        "quick_summary_jobs",
        [
            "tenant_id",
            "created_at",
        ],
    )

    op.create_index(
        "ix_quick_summary_jobs_status_next",
        "quick_summary_jobs",
        [
            "status",
            "next_attempt_at",
        ],
    )

    op.create_index(
        "uq_quick_summary_jobs_tenant_idempotency",
        "quick_summary_jobs",
        [
            "tenant_id",
            "idempotency_key",
        ],
        unique=True,
        postgresql_where=sa.text(
            "idempotency_key IS NOT NULL"
        ),
    )

    op.create_table(
        "learning_material_jobs",

        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),

        sa.Column(
            "tenant_id",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "idempotency_key",
            sa.String(128),
            nullable=True,
        ),

        sa.Column(
            "idempotency_hash",
            sa.String(64),
            nullable=True,
        ),

        sa.Column(
            "video_id",
            sa.String(36),
            sa.ForeignKey(
                "videos.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "transcript_id",
            sa.String(36),
            sa.ForeignKey(
                "transcripts.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),

        sa.Column(
            "transcription_job_id",
            sa.String(36),
            sa.ForeignKey(
                "transcription_jobs.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),

        sa.Column(
            "source_etag",
            sa.String(256),
            nullable=True,
        ),

        sa.Column(
            "fingerprint",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "notes_style",
            sa.String(32),
            nullable=False,
        ),

        sa.Column(
            "include_mind_map",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "include_flowchart",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
        ),

        sa.Column(
            "model_id",
            sa.String(512),
            nullable=False,
        ),

        sa.Column(
            "algorithm_version",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "content",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "mind_map",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "flowchart",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "component_status",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "component_errors",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),

        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "error_code",
            sa.String(128),
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
            server_default=sa.func.now(),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
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
    )

    op.create_index(
        "ix_learning_material_jobs_tenant_created",
        "learning_material_jobs",
        [
            "tenant_id",
            "created_at",
        ],
    )

    op.create_index(
        "ix_learning_material_jobs_status_next",
        "learning_material_jobs",
        [
            "status",
            "next_attempt_at",
        ],
    )

    op.create_index(
        "uq_learning_material_jobs_tenant_idempotency",
        "learning_material_jobs",
        [
            "tenant_id",
            "idempotency_key",
        ],
        unique=True,
        postgresql_where=sa.text(
            "idempotency_key IS NOT NULL"
        ),
    )


def downgrade():
    op.drop_index(
        "uq_learning_material_jobs_tenant_idempotency",
        table_name="learning_material_jobs",
    )

    op.drop_index(
        "ix_learning_material_jobs_status_next",
        table_name="learning_material_jobs",
    )

    op.drop_index(
        "ix_learning_material_jobs_tenant_created",
        table_name="learning_material_jobs",
    )

    op.drop_table(
        "learning_material_jobs"
    )

    op.drop_index(
        "uq_quick_summary_jobs_tenant_idempotency",
        table_name="quick_summary_jobs",
    )

    op.drop_index(
        "ix_quick_summary_jobs_status_next",
        table_name="quick_summary_jobs",
    )

    op.drop_index(
        "ix_quick_summary_jobs_tenant_created",
        table_name="quick_summary_jobs",
    )

    op.drop_table(
        "quick_summary_jobs"
    )
