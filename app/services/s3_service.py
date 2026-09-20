"""AWS S3 access through boto3.

Credentials are never passed in code. boto3 looks for them in this order:
environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) -> ~/.aws/credentials
-> an IAM role attached to the machine or container.
"""
import logging
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.errors import DocumentNotFoundError, StorageError

logger = logging.getLogger("regflow.s3")


@lru_cache
def get_s3_client():
    return boto3.client("s3", region_name=get_settings().aws_region)


def upload_document(file_bytes: bytes, object_key: str, content_type: str = "application/pdf") -> str:
    """Upload bytes to the configured bucket and return the object key."""
    bucket = get_settings().s3_bucket_name
    try:
        get_s3_client().put_object(
            Bucket=bucket, Key=object_key, Body=file_bytes, ContentType=content_type
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 upload failed for s3://%s/%s: %s", bucket, object_key, exc)
        raise StorageError(f"Could not upload the document to S3: {exc}") from exc
    logger.info("Uploaded s3://%s/%s", bucket, object_key)
    return object_key


def download_document(object_key: str) -> bytes:
    """Download an object from the configured bucket."""
    bucket = get_settings().s3_bucket_name
    try:
        response = get_s3_client().get_object(Bucket=bucket, Key=object_key)
        return response["Body"].read()
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            raise DocumentNotFoundError(f"s3://{bucket}/{object_key} does not exist.") from exc
        logger.error("S3 download failed for s3://%s/%s: %s", bucket, object_key, exc)
        raise StorageError(f"Could not download the document from S3: {exc}") from exc
    except BotoCoreError as exc:
        logger.error("S3 download failed for s3://%s/%s: %s", bucket, object_key, exc)
        raise StorageError(f"Could not download the document from S3: {exc}") from exc
