from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

from loguru import logger
from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error

from app.core.exceptions import AppError


class StorageError(AppError):
    def __init__(self, detail: str = "Storage error") -> None:
        super().__init__(detail=detail, code="STORAGE_ERROR", status_code=500)


class StorageService:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False, public_url: str | None = None) -> None:
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket
        self._endpoint = endpoint
        self._public_url = (public_url or f"{'https' if secure else 'http'}://{endpoint}").rstrip("/")

    async def ensure_bucket(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            exists = await loop.run_in_executor(None, self._client.bucket_exists, self._bucket)
            if not exists:
                await loop.run_in_executor(None, self._client.make_bucket, self._bucket)
        except S3Error as exc:
            raise StorageError(f"Failed to ensure bucket: {exc}") from exc

    async def set_bucket_public(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self._bucket}/*"],
                    }
                ],
            }
            await loop.run_in_executor(
                None,
                lambda: self._client.set_bucket_policy(self._bucket, json.dumps(policy)),
            )
        except S3Error as exc:
            raise StorageError(f"Failed to set bucket public policy: {exc}") from exc

    def get_public_url(self, file_name: str) -> str:
        return f"{self._public_url}/{self._bucket}/{file_name}"

    def get_storage_path(self, file_name: str) -> str:
        return f"{self._bucket}/{file_name}"

    def resolve_image_url(self, path: str) -> str:
        if path.startswith("http"):
            path = path.split("/", 3)[-1]
        return f"{self._public_url}/{path}"

    @staticmethod
    def strip_domain(url: str) -> str:
        if url.startswith("http"):
            return url.split("/", 3)[-1]
        return url

    async def upload_file(
        self,
        file_name: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._client.put_object(
                    self._bucket,
                    file_name,
                    io.BytesIO(data),
                    length=len(data),
                    content_type=content_type,
                    metadata=metadata or {},  # type: ignore[arg-type]
                ),
            )
            return result.object_name
        except S3Error as exc:
            raise StorageError(f"Failed to upload file: {exc}") from exc

    async def get_file(self, file_name: str) -> bytes | None:
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.get_object(self._bucket, file_name),
            )
            data = await loop.run_in_executor(None, response.read)
            response.close()
            response.release_conn()
            return data
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise StorageError(f"Failed to get file: {exc}") from exc

    async def delete_file(self, file_name: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.remove_object(self._bucket, file_name),
            )
        except S3Error as exc:
            if exc.code != "NoSuchKey":
                raise StorageError(f"Failed to delete file: {exc}") from exc

    async def get_presigned_url(self, file_name: str, expires: int = 3600) -> str:
        loop = asyncio.get_running_loop()
        try:
            url = await loop.run_in_executor(
                None,
                lambda: self._client.presigned_get_object(self._bucket, file_name, expires=timedelta(seconds=expires)),
            )
            return url
        except S3Error as exc:
            raise StorageError(f"Failed to generate presigned URL: {exc}") from exc

    async def stat_file(self, file_name: str) -> dict[str, Any] | None:
        loop = asyncio.get_running_loop()
        try:
            stat = await loop.run_in_executor(
                None,
                lambda: self._client.stat_object(self._bucket, file_name),
            )
            return {
                "size": stat.size,
                "content_type": stat.content_type or "application/octet-stream",
                "metadata": stat.metadata,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            }
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise StorageError(f"Failed to stat file: {exc}") from exc

    async def list_files(self, prefix: str = "") -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        try:
            objects = await loop.run_in_executor(
                None,
                lambda: list(self._client.list_objects(self._bucket, prefix=prefix, recursive=True)),
            )
            return [
                {
                    "file_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "content_type": obj.content_type or "application/octet-stream",
                }
                for obj in objects
            ]
        except S3Error as exc:
            raise StorageError(f"Failed to list files: {exc}") from exc

    async def cross_bucket_move(self, source_storage: StorageService, source_name: str, dest_name: str) -> str:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.copy_object(
                    self._bucket,
                    dest_name,
                    CopySource(source_storage._bucket, source_name),
                ),
            )
            await loop.run_in_executor(
                None,
                lambda: source_storage._client.remove_object(source_storage._bucket, source_name),
            )
            return dest_name
        except S3Error as exc:
            raise StorageError(f"Failed to move file across buckets: {exc}") from exc

    async def move_file(self, source_name: str, dest_name: str) -> str:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.copy_object(
                    self._bucket,
                    dest_name,
                    CopySource(self._bucket, source_name),
                ),
            )
            await loop.run_in_executor(
                None,
                lambda: self._client.remove_object(self._bucket, source_name),
            )
            return dest_name
        except S3Error as exc:
            raise StorageError(f"Failed to move file: {exc}") from exc

    async def delete_files_by_prefix(self, prefix: str) -> int:
        loop = asyncio.get_running_loop()
        try:
            objects = await loop.run_in_executor(
                None,
                lambda: list(self._client.list_objects(self._bucket, prefix=prefix, recursive=True)),
            )
            if not objects:
                return 0
            names = [o.object_name for o in objects]
            errors = await loop.run_in_executor(
                None,
                lambda: self._client.remove_objects(self._bucket, names),
            )
            error_list = await loop.run_in_executor(None, list, errors or [])
            return len(names) - len(error_list)
        except S3Error as exc:
            raise StorageError(f"Failed to delete files by prefix: {exc}") from exc

    async def download_file_iterator(self, file_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.get_object(self._bucket, file_name),
            )
            while True:
                chunk = await loop.run_in_executor(None, response.read, chunk_size)
                if not chunk:
                    break
                yield chunk
            response.close()
            response.release_conn()
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return
            raise StorageError(f"Failed to stream file: {exc}") from exc


async def move_url_to_bucket(url: str, source_storage: StorageService | None, dest_storage: StorageService | None) -> str:
    """If `url` lives in source_storage's bucket, move it to dest_storage's bucket and return the new URL.

    Returns the original URL unchanged if either storage is unavailable or the URL is not in the source bucket.
    """
    if not source_storage or not dest_storage:
        return url
    prefix = f"{source_storage._public_url}/{source_storage._bucket}/"
    if not url.startswith(prefix):
        return url
    file_name = url[len(prefix) :]
    if not file_name:
        return url
    try:
        await dest_storage.cross_bucket_move(source_storage, file_name, file_name)
        return dest_storage.get_public_url(file_name)
    except Exception:
        logger.exception("cross_bucket_move failed for {}", file_name)
        return url
