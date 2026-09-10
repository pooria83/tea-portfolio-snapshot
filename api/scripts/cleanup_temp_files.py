#!/usr/bin/env python3
"""
Clean up temp files in MinIO that are older than 1 hour.
Optionally cross-checks against product_images table to avoid removing orphaned data.

Usage:
    python scripts/cleanup_temp_files.py                    # dry run (default)
    python scripts/cleanup_temp_files.py --apply            # actually delete
    python scripts/cleanup_temp_files.py --apply --db-check # check product_images table too
    python scripts/cleanup_temp_files.py --max-age 3600     # delete files older than N seconds
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from loguru import logger
from minio import Minio
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.repositories.product_definition import ProductImageRepository

logger.add(sys.stderr, level="INFO")


async def get_used_image_urls(db_url: str) -> set[str]:
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    used: set[str] = set()
    async with session_factory() as session:
        used = set(await ProductImageRepository(session).list_temp_urls())
    await engine.dispose()
    return used


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up temp files in MinIO")
    parser.add_argument("--apply", action="store_true", help="Actually delete files (default: dry-run)")
    parser.add_argument("--db-check", action="store_true", help="Cross-check against product_images table")
    parser.add_argument("--max-age", type=int, default=3600, help="Max age in seconds (default: 3600)")
    args = parser.parse_args()

    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=args.max_age)

    bucket = settings.minio_temp_bucket
    logger.info(
        "MinIO {} bucket={} cutoff={} apply={} db_check={}",
        settings.minio_endpoint,
        bucket,
        cutoff.isoformat(),
        args.apply,
        args.db_check,
    )

    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )

    try:
        if not client.bucket_exists(bucket):
            logger.info("Bucket {} does not exist — nothing to clean", bucket)
            return
    except S3Error:
        logger.info("Bucket {} does not exist — nothing to clean", bucket)
        return

    used_urls: set[str] = set()
    if args.db_check:
        try:
            used_urls = asyncio.run(get_used_image_urls(settings.database_url))
            logger.info("Found {} temp/ URLs referenced in product_images table", len(used_urls))
        except Exception as exc:
            logger.warning("DB check failed, skipping: {}", exc)

    objects = list(client.list_objects(bucket, prefix="", recursive=True))
    logger.info("Found {} objects in bucket {}", len(objects), bucket)

    deletable = []
    for obj in objects:
        if obj.last_modified is not None and obj.last_modified < cutoff:
            if args.db_check and obj.object_name in used_urls:
                logger.debug("Skipping {} (referenced in product_images)", obj.object_name)
                continue
            deletable.append(obj.object_name)

    if not deletable:
        logger.info("No deletable files found")
        return

    logger.info("Files to delete: {}", len(deletable))
    for name in deletable:
        logger.info("  {}", name)

    if args.apply:
        errors = client.remove_objects(bucket, deletable)
        error_list = list(errors or [])
        deleted_count = len(deletable) - len(error_list)
        logger.info("Deleted {} files", deleted_count)
        for err in error_list:
            logger.error("Delete error: {}", err)
    else:
        logger.info("Dry run — pass --apply to actually delete")


if __name__ == "__main__":
    main()
