import uuid
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import BinaryIO

from app.core.config import settings


def _get_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


async def upload_contract_file(
    file_content: bytes,
    original_filename: str,
    user_id: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload contract file to S3 and return the S3 key."""
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    s3_key = f"contracts/{user_id}/{uuid.uuid4()}.{ext}"

    client = _get_client()
    try:
        client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"FILE_UPLOAD_FAILED: {e}") from e

    return s3_key


def get_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for downloading a file."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def get_file_content(s3_key: str) -> bytes:
    """Download a file from S3 and return its content."""
    client = _get_client()
    response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    return response["Body"].read()
