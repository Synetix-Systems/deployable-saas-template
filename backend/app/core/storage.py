"""S3-compatible object storage helper (boto3).

Works against AWS S3, MinIO, Backblaze B2, or any S3 API. Configure via the
`S3_*` settings. For real AWS S3 leave `S3_ENDPOINT_URL` empty; for MinIO/other
set it to the endpoint URL (path-style addressing + SigV4 are forced, which
MinIO requires).
"""

import logging
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

_s3_client = None


def get_s3_client():
    """Return a lazily-initialised, module-cached S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 2},
            ),
        )
    return _s3_client


def ensure_bucket(bucket: str | None = None) -> None:
    """Create the bucket if it does not already exist (idempotent)."""
    bucket = bucket or settings.S3_BUCKET_NAME
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)
        logger.info("created bucket %s", bucket)


def upload_fileobj(
    fileobj: BinaryIO,
    key: str,
    *,
    bucket: str | None = None,
    content_type: str | None = None,
) -> str:
    """Upload a file-like object and return its key."""
    bucket = bucket or settings.S3_BUCKET_NAME
    extra = {"ContentType": content_type} if content_type else {}
    get_s3_client().upload_fileobj(fileobj, bucket, key, ExtraArgs=extra)
    return key


def download_fileobj(key: str, fileobj: BinaryIO, *, bucket: str | None = None) -> None:
    """Download an object into a file-like object."""
    bucket = bucket or settings.S3_BUCKET_NAME
    get_s3_client().download_fileobj(bucket, key, fileobj)


def presigned_url(key: str, *, bucket: str | None = None, expires: int = 3600) -> str:
    """Return a time-limited GET URL for an object."""
    bucket = bucket or settings.S3_BUCKET_NAME
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
