"""
SecureStego — Storage Service

Unified file storage interface with two backends:
  - **Local**: Filesystem-based (default for dev/testing, no external deps).
  - **S3**: S3-compatible object storage (AWS S3 free tier or MinIO locally).

The backend is selected via config (STORAGE_BACKEND="local" or "s3").
When STORAGE_BACKEND="s3", the service uses boto3 against whatever endpoint
is configured in S3_ENDPOINT_URL — this works identically for real AWS S3
and for a local MinIO container (same S3 API, different endpoint).

Signed URLs:
  - S3 backend generates pre-signed download URLs with configurable expiry
    (default 15 minutes). These are time-limited and do not require auth.
  - Local backend returns a server-relative path served by FastAPI.

S3 Lifecycle Rules (documented, not automated):
  Recommended: Configure a lifecycle rule on the S3 bucket to auto-delete
  objects older than 30 days. This can be done via:
    - AWS Console → S3 → Bucket → Management → Lifecycle rules
    - MinIO: mc ilm rule add ALIAS/BUCKET --expiry-days 30
  See docs/ARCHITECTURE.md for full instructions.
"""

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Signed URL expiry in seconds (15 minutes)
SIGNED_URL_EXPIRY = 900


# ---------------------------------------------------------------------------
# Local filesystem backend
# ---------------------------------------------------------------------------

def _ensure_storage_dir() -> Path:
    """Ensure the local storage directory exists."""
    storage_dir = Path(settings.storage_local_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


async def _local_upload(source_path: str, original_filename: str) -> tuple[str, str]:
    """Upload to local filesystem."""
    storage_dir = _ensure_storage_dir()
    ext = os.path.splitext(original_filename)[1] or ".png"
    storage_key = f"{uuid.uuid4().hex}{ext}"
    dest_path = storage_dir / storage_key
    shutil.copy2(source_path, dest_path)
    download_url = f"/storage/{storage_key}"
    return storage_key, download_url


async def _local_get_path(storage_key: str) -> str:
    """Get local filesystem path for a stored file."""
    storage_dir = _ensure_storage_dir()
    file_path = storage_dir / storage_key
    if not file_path.exists():
        raise FileNotFoundError(f"File not found in storage: {storage_key}")
    return str(file_path.resolve())


async def _local_get_download_url(storage_key: str) -> str:
    """Get download URL for a locally stored file."""
    return f"/storage/{storage_key}"


async def _local_delete(storage_key: str) -> None:
    """Delete a file from local storage."""
    storage_dir = _ensure_storage_dir()
    file_path = storage_dir / storage_key
    if file_path.exists():
        file_path.unlink()

def _local_stream(storage_key: str):
    storage_dir = _ensure_storage_dir()
    file_path = storage_dir / storage_key
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {storage_key}")
    return open(file_path, "rb")


# ---------------------------------------------------------------------------
# S3-compatible backend (AWS S3 / MinIO)
# ---------------------------------------------------------------------------

def _get_s3_client():
    """Create a boto3 S3 client configured from settings.

    Works against real AWS S3 (when S3_ENDPOINT_URL is not set or is an
    AWS endpoint) and against MinIO (when S3_ENDPOINT_URL points to the
    MinIO container, e.g., http://localhost:9000).
    """
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        # Required for MinIO path-style access
        config=boto3.session.Config(signature_version="s3v4"),
    )


def _ensure_s3_bucket(client) -> None:
    """Create the S3 bucket if it doesn't exist (idempotent)."""
    try:
        client.head_bucket(Bucket=settings.s3_bucket_name)
    except Exception:
        try:
            client.create_bucket(Bucket=settings.s3_bucket_name)
            logger.info("Created S3 bucket: %s", settings.s3_bucket_name)
        except Exception as e:
            # Bucket may already exist (race condition) or we lack permissions
            logger.warning("Could not create S3 bucket: %s", e)


async def _s3_upload(source_path: str, original_filename: str) -> tuple[str, str]:
    """Upload a file to S3/MinIO and return a pre-signed download URL."""
    ext = os.path.splitext(original_filename)[1] or ".png"
    storage_key = f"{uuid.uuid4().hex}{ext}"

    client = _get_s3_client()
    _ensure_s3_bucket(client)

    # Upload the file
    client.upload_file(
        source_path,
        settings.s3_bucket_name,
        storage_key,
        ExtraArgs={"ContentType": "image/png"},
    )

    # Generate pre-signed download URL (15-minute expiry)
    download_url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": storage_key},
        ExpiresIn=SIGNED_URL_EXPIRY,
    )

    logger.info("Uploaded to S3: %s (signed URL expires in %ds)", storage_key, SIGNED_URL_EXPIRY)
    return storage_key, download_url


async def _s3_get_download_url(storage_key: str) -> str:
    """Generate a fresh pre-signed URL for an existing S3 object."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": storage_key},
        ExpiresIn=SIGNED_URL_EXPIRY,
    )


async def _s3_get_path(storage_key: str) -> str:
    """Download from S3 to a temp file and return the local path.

    This is needed for the decode endpoint which needs a local file path
    for OpenCV to read. The temp file is in the configured local storage dir.
    """
    import tempfile
    client = _get_s3_client()
    storage_dir = _ensure_storage_dir()
    local_path = storage_dir / f"tmp_{storage_key}"
    client.download_file(settings.s3_bucket_name, storage_key, str(local_path))
    return str(local_path)


async def _s3_delete(storage_key: str) -> None:
    """Delete an object from S3."""
    client = _get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket_name, Key=storage_key)

def _s3_stream(storage_key: str):
    client = _get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket_name, Key=storage_key)
    return response['Body']


# ---------------------------------------------------------------------------
# Public unified interface — dispatches to the configured backend
# ---------------------------------------------------------------------------

def initialize_storage() -> None:
    """Initialize the configured storage backend (e.g., auto-create bucket on startup)."""
    if settings.storage_backend == "s3":
        client = _get_s3_client()
        _ensure_s3_bucket(client)
    else:
        _ensure_storage_dir()

async def upload_file(source_path: str, original_filename: str) -> tuple[str, str]:
    """Upload a file to the configured storage backend.

    Args:
        source_path: Path to the file to upload.
        original_filename: Original filename (for extension preservation).

    Returns:
        (storage_key, download_url) — the key for retrieval, and a download URL.
        For S3: download_url is a pre-signed URL with 15-minute expiry.
        For local: download_url is a server-relative path.
    """
    if settings.storage_backend == "s3":
        return await _s3_upload(source_path, original_filename)
    return await _local_upload(source_path, original_filename)


async def get_file_path(storage_key: str) -> str:
    """Get a local filesystem path to a stored file.

    For S3 backend, this downloads the file to a temp location first.

    Args:
        storage_key: The storage key returned by upload_file.

    Returns:
        Absolute path to the file on disk.
    """
    if settings.storage_backend == "s3":
        return await _s3_get_path(storage_key)
    return await _local_get_path(storage_key)


async def get_download_url(storage_key: str) -> str:
    """Get a download URL for a stored file.

    For S3: generates a fresh pre-signed URL (15-minute expiry).
    For local: returns the server-relative path.

    Args:
        storage_key: The storage key.

    Returns:
        Download URL string.
    """
    if settings.storage_backend == "s3":
        return await _s3_get_download_url(storage_key)
    return await _local_get_download_url(storage_key)


async def delete_file(storage_key: str) -> None:
    """Delete a file from the configured storage backend.

    Args:
        storage_key: The storage key to delete.
    """
    if settings.storage_backend == "s3":
        return await _s3_delete(storage_key)
    return await _local_delete(storage_key)

def stream_file(storage_key: str):
    """Return a file-like object for streaming."""
    if settings.storage_backend == "s3":
        return _s3_stream(storage_key)
    return _local_stream(storage_key)
