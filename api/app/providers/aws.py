from functools import lru_cache

import boto3

from app.core.config import get_settings


@lru_cache
def aws_session():
    settings = get_settings()

    kwargs = {
        "region_name":
            settings.aws_region
    }

    if settings.aws_profile:
        kwargs["profile_name"] = (
            settings.aws_profile
        )

    return boto3.Session(
        **kwargs
    )


@lru_cache
def s3_client():
    return aws_session().client(
        "s3"
    )


@lru_cache
def transcribe_client():
    return aws_session().client(
        "transcribe"
    )


@lru_cache
def bedrock_runtime_client():
    settings = get_settings()

    return aws_session().client(
        "bedrock-runtime",
        region_name=(
            settings.bedrock_region
            or settings.aws_region
        ),
    )


@lru_cache
def sqs_client():
    settings = get_settings()

    return aws_session().client(
        "sqs",
        region_name=settings.aws_region,
    )
