from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "DT-FlashCut API"
    app_env: str = "production"
    app_version: str = "1.0.0"

    aws_region: str
    aws_profile: str | None = None

    s3_bucket: str
    s3_video_prefix: str = "videos/"
    s3_tenant_prefix_template: str | None = None
    s3_output_prefix: str = "generated/"
    s3_transcript_prefix: str = "transcripts/"
    s3_render_asset_prefix: str = "render-assets/"

    database_url: str

    transcribe_language: str = "en-US"
    transcribe_vocabulary: str | None = None
    transcribe_config_version: str = "v1"

    bedrock_region: str | None = None
    bedrock_model_id: str
    summary_algorithm_version: str = "v3.1"
    notes_algorithm_version: str = "v1"
    quick_summary_algorithm_version: str = "v1"
    learning_material_algorithm_version: str = "v1"

    quick_summary_queue_url: str
    learning_material_queue_url: str

    generation_visibility_timeout_seconds: int = 300
    generation_heartbeat_interval_seconds: int = 60
    generation_queue_publish_max_attempts: int = 20
    generation_dispatch_poll_seconds: float = 0.5
    generation_outbox_batch_size: int = 20
    generation_max_attempts: int = 3
    generation_worker_poll_seconds: float = 1.0
    generation_stale_after_seconds: int = 180

    render_queue_url: str
    render_profile_version: str = "v2"
    render_presign_seconds: int = 900
    render_max_clips: int = 500
    render_max_total_seconds: int = 7200
    render_ffmpeg_timeout_seconds: int = 3600

    render_asset_upload_presign_seconds: int = 900
    render_asset_max_bytes: int = 104_857_600
    render_asset_max_duration_seconds: int = 60

    render_visibility_timeout_seconds: int = 300
    render_heartbeat_interval_seconds: int = 60
    render_stale_after_seconds: int = 600
    render_queue_publish_max_attempts: int = 20

    local_output_dir: str | None = None

    auth_disabled: bool = False
    local_tenant_id: str = "local-development"

    auth_jwt_issuer: str | None = None
    auth_jwt_audience: str | None = None
    auth_jwks_url: str | None = None

    auth_tenant_claim: str = "custom:tenant_id"
    auth_subject_claim: str = "sub"

    auth_jwt_audience_claim: str = "client_id"
    auth_jwt_token_use: str | None = "access"
    auth_jwt_algorithms: str = "RS256"
    auth_clock_skew_seconds: int = 60

    trusted_hosts: str = "*"

    redis_url: str | None = None
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 300
    rate_limit_write_requests_per_minute: int = 60

    max_video_list: int = 5000
    max_request_bytes: int = 2_000_000

    @model_validator(mode="after")
    def validate_authentication(self):
        environment = (
            self.app_env
            .strip()
            .lower()
        )

        if (
            environment == "production"
            and self.auth_disabled
        ):
            raise ValueError(
                "AUTH_DISABLED cannot be true "
                "when APP_ENV=production"
            )

        if (
            self.rate_limit_enabled
            and not self.redis_url
        ):
            raise ValueError(
                "REDIS_URL is required when "
                "RATE_LIMIT_ENABLED=true"
            )

        if (
            self.rate_limit_requests_per_minute
            < 1
            or self.rate_limit_write_requests_per_minute
            < 1
        ):
            raise ValueError(
                "Rate limits must be positive."
            )

        if self.max_request_bytes < 1024:
            raise ValueError(
                "MAX_REQUEST_BYTES is too small."
            )

        if environment == "production":
            hosts = [
                item.strip()
                for item
                in self.trusted_hosts.split(",")
                if item.strip()
            ]

            if (
                not hosts
                or "*" in hosts
            ):
                raise ValueError(
                    "TRUSTED_HOSTS must be explicit "
                    "when APP_ENV=production"
                )

            if not self.rate_limit_enabled:
                raise ValueError(
                    "RATE_LIMIT_ENABLED must be true "
                    "when APP_ENV=production"
                )

        if not self.auth_disabled:
            missing = []

            if not self.auth_jwt_issuer:
                missing.append(
                    "AUTH_JWT_ISSUER"
                )

            if not self.auth_jwt_audience:
                missing.append(
                    "AUTH_JWT_AUDIENCE"
                )

            if not self.auth_tenant_claim:
                missing.append(
                    "AUTH_TENANT_CLAIM"
                )

            if missing:
                raise ValueError(
                    "Authentication configuration "
                    "is incomplete: "
                    + ", ".join(missing)
                )

        return self


    @property
    def trusted_host_list(
        self,
    ) -> list[str]:
        hosts = [
            item.strip()
            for item
            in self.trusted_hosts.split(",")
            if item.strip()
        ]

        return (
            hosts
            or ["*"]
        )


    @field_validator(
        "s3_video_prefix",
        "s3_output_prefix",
        "s3_transcript_prefix",
        "s3_render_asset_prefix",
    )
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        value = value.strip().lstrip("/")

        if not value:
            raise ValueError(
                "S3 prefix cannot be empty"
            )

        if not value.endswith("/"):
            value += "/"

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
