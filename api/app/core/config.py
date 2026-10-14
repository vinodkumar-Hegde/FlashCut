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

    database_url: str

    transcribe_language: str = "en-US"
    transcribe_vocabulary: str | None = None
    transcribe_config_version: str = "v1"

    bedrock_region: str | None = None
    bedrock_model_id: str
    summary_algorithm_version: str = "v3.1"
    notes_algorithm_version: str = "v1"

    render_queue_url: str
    render_profile_version: str = "v1"
    render_presign_seconds: int = 900
    render_max_clips: int = 500
    render_max_total_seconds: int = 7200
    render_ffmpeg_timeout_seconds: int = 3600

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


    @field_validator(
        "s3_video_prefix",
        "s3_output_prefix",
        "s3_transcript_prefix",
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
