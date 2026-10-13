from functools import lru_cache

from pydantic import field_validator
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
    s3_output_prefix: str = "generated/"
    s3_transcript_prefix: str = "transcripts/"

    database_url: str

    transcribe_language: str = "en-US"
    transcribe_vocabulary: str | None = None

    bedrock_region: str | None = None
    bedrock_model_id: str
    summary_algorithm_version: str = "v3.1"

    render_queue_url: str
    render_profile_version: str = "v1"
    render_presign_seconds: int = 900
    render_max_clips: int = 500
    render_max_total_seconds: int = 7200
    render_ffmpeg_timeout_seconds: int = 3600
    local_output_dir: str | None = None

    auth_disabled: bool = False

    max_video_list: int = 5000
    max_request_bytes: int = 2_000_000

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
