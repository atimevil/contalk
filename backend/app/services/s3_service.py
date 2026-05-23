"""
S3 파일 서비스.

AWS 자격증명이 없는 개발 환경에서는 로컬 파일시스템을 S3 대신 사용한다.
  LOCAL_UPLOAD_DIR 환경변수로 저장 디렉토리를 설정한다 (기본: /tmp/contalktok_uploads).
"""
import os
import uuid
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _is_local_mode() -> bool:
    """AWS 자격증명이 없으면 로컬 모드로 동작한다."""
    return not (os.environ.get("AWS_ACCESS_KEY_ID", "").strip())


def _get_local_upload_dir() -> Path:
    """로컬 업로드 디렉토리 경로를 반환하고 없으면 생성한다."""
    upload_dir = Path(os.environ.get("LOCAL_UPLOAD_DIR", "/tmp/contalktok_uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


# ─────────────────────────────────────────────────────────────────────────────
# S3 클라이언트 팩토리
# ─────────────────────────────────────────────────────────────────────────────

def _get_client():
    """boto3 S3 클라이언트를 반환한다."""
    import boto3
    from app.core.config import settings

    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 퍼블릭 인터페이스
# ─────────────────────────────────────────────────────────────────────────────

async def upload_contract_file(
    file_content: bytes,
    original_filename: str,
    user_id: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    계약서 파일을 S3(또는 로컬)에 업로드하고 키(경로)를 반환한다.

    Returns
    -------
    str
        S3 key 또는 로컬 파일 절대경로 (pipeline._download_from_s3 의 폴백에서 사용됨)
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    unique_name = f"{uuid.uuid4()}.{ext}"

    if _is_local_mode():
        return _local_upload(file_content, user_id, unique_name)
    else:
        return _s3_upload(file_content, user_id, unique_name, content_type)


def get_presigned_url(s3_key: str, expires_in: int = 3600) -> Optional[str]:
    """
    S3 presigned URL을 반환한다.
    로컬 모드에서는 None을 반환한다 (직접 접근 불가).
    """
    if _is_local_mode():
        logger.debug("로컬 모드 — presigned URL 생성 불가: %s", s3_key)
        return None

    client = _get_client()
    from app.core.config import settings

    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def get_file_content(s3_key: str) -> bytes:
    """
    S3(또는 로컬)에서 파일 내용을 읽어 반환한다.
    """
    if _is_local_mode():
        return _local_read(s3_key)
    else:
        return _s3_download(s3_key)


# ─────────────────────────────────────────────────────────────────────────────
# 내부 구현 — S3
# ─────────────────────────────────────────────────────────────────────────────

def _s3_upload(
    file_content: bytes,
    user_id: str,
    unique_name: str,
    content_type: str,
) -> str:
    """S3에 파일을 업로드하고 key를 반환한다."""
    from botocore.exceptions import BotoCoreError, ClientError
    from app.core.config import settings

    s3_key = f"contracts/{user_id}/{unique_name}"
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

    logger.info("S3 업로드 완료: %s (%d bytes)", s3_key, len(file_content))
    return s3_key


def _s3_download(s3_key: str) -> bytes:
    """S3에서 파일을 다운로드하고 내용을 반환한다."""
    from app.core.config import settings

    client = _get_client()
    response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    return response["Body"].read()


# ─────────────────────────────────────────────────────────────────────────────
# 내부 구현 — 로컬 파일시스템
# ─────────────────────────────────────────────────────────────────────────────

def _local_upload(file_content: bytes, user_id: str, unique_name: str) -> str:
    """로컬 파일시스템에 파일을 저장하고 절대경로를 반환한다."""
    upload_dir = _get_local_upload_dir()
    user_dir = upload_dir / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    file_path = user_dir / unique_name
    file_path.write_bytes(file_content)

    logger.info(
        "로컬 파일 저장 완료 (AWS 자격증명 없음): %s (%d bytes)",
        file_path,
        len(file_content),
    )
    return str(file_path)


def _local_read(path: str) -> bytes:
    """로컬 파일을 읽어 반환한다."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"로컬 파일을 찾을 수 없습니다: {path}")
    return file_path.read_bytes()
