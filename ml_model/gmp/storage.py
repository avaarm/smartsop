"""Pluggable storage for generated documents.

Generated DOCX files must not be pinned to the local disk of one backend
instance, or a file created on instance A can't be downloaded from instance B.
This module abstracts persistence behind ``DocumentStorage`` with two backends:

- ``local`` (default): writes to a directory. Fine for a single instance or a
  shared/network volume.
- ``s3``: stores objects in S3 (or any S3-compatible store) and serves them via
  short-lived presigned URLs, which keeps the app stateless and offloads the
  download bytes from the app process.

Select with ``DOCUMENT_STORAGE=local|s3``.
"""

import os
import logging
from pathlib import Path

from flask import send_file, redirect
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

DOCX_MIMETYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DEFAULT_LOCAL_DIR = Path(__file__).parent.parent.parent / "generated_docs"


class DocumentStorage:
    """Interface for persisting and serving generated documents."""

    def save(self, filename: str, data: bytes) -> None:
        raise NotImplementedError

    def exists(self, filename: str) -> bool:
        raise NotImplementedError

    def download_response(self, filename: str):
        """Return a Flask response that delivers the file, or None if missing."""
        raise NotImplementedError


class LocalDocumentStorage(DocumentStorage):
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, filename: str):
        safe = secure_filename(filename)
        if not safe:
            return None
        return self.directory / safe

    def save(self, filename: str, data: bytes) -> None:
        path = self._safe_path(filename)
        if path is None:
            raise ValueError(f"Invalid filename: {filename!r}")
        with open(path, "wb") as f:
            f.write(data)

    def exists(self, filename: str) -> bool:
        path = self._safe_path(filename)
        return path is not None and path.is_file()

    def download_response(self, filename: str):
        path = self._safe_path(filename)
        if path is None or not path.is_file():
            return None
        return send_file(path, as_attachment=True, download_name=path.name)


class S3DocumentStorage(DocumentStorage):
    def __init__(self, bucket: str, prefix: str = "", region=None,
                 endpoint_url=None, presign_expiry: int = 900):
        try:
            import boto3  # lazy: only needed when S3 is selected
        except ImportError as e:
            raise RuntimeError(
                "DOCUMENT_STORAGE=s3 requires boto3 — install it with `pip install boto3`."
            ) from e
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.presign_expiry = presign_expiry
        self._client = boto3.client("s3", region_name=region, endpoint_url=endpoint_url)

    def _key(self, filename: str) -> str:
        safe = secure_filename(filename)
        return f"{self.prefix}/{safe}" if self.prefix else safe

    def save(self, filename: str, data: bytes) -> None:
        self._client.put_object(
            Bucket=self.bucket, Key=self._key(filename),
            Body=data, ContentType=DOCX_MIMETYPE,
        )

    def exists(self, filename: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._key(filename))
            return True
        except Exception:
            return False

    def download_response(self, filename: str):
        if not self.exists(filename):
            return None
        safe = secure_filename(filename)
        url = self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": self._key(filename),
                "ResponseContentDisposition": f'attachment; filename="{safe}"',
            },
            ExpiresIn=self.presign_expiry,
        )
        return redirect(url)


_storage = None


def get_document_storage() -> DocumentStorage:
    """Return the process-wide storage backend, configured from the environment."""
    global _storage
    if _storage is not None:
        return _storage

    backend = os.environ.get("DOCUMENT_STORAGE", "local").lower()
    if backend == "s3":
        bucket = os.environ.get("S3_BUCKET")
        if not bucket:
            raise RuntimeError("DOCUMENT_STORAGE=s3 requires S3_BUCKET to be set")
        _storage = S3DocumentStorage(
            bucket=bucket,
            prefix=os.environ.get("S3_PREFIX", ""),
            region=os.environ.get("AWS_REGION"),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
            presign_expiry=int(os.environ.get("S3_PRESIGN_EXPIRY", 900)),
        )
        logger.info("Document storage: S3 bucket=%s prefix=%s", bucket, os.environ.get("S3_PREFIX", ""))
    else:
        directory = os.environ.get("GENERATED_DOCS_DIR", str(DEFAULT_LOCAL_DIR))
        _storage = LocalDocumentStorage(directory)
        logger.info("Document storage: local dir=%s", directory)
    return _storage
