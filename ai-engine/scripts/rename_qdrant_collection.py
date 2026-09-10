"""One-time migration: rename the legacy single Qdrant 'products' collection to the per-model name.

The AI Engine now uses per-model collection names (``products-{model-slug}``).
The legacy collection holds vectors produced by the current default embedding
model, so instead of re-embedding everything we copy it into the new per-model
collection and drop the legacy one.

Safe to re-run: point ids are deterministic (``uuid5(product_id_lang)``), so
the upsert into the new collection is idempotent and never duplicates points.

Usage:
    uv run python scripts/rename_qdrant_collection.py            # migrate
    uv run python scripts/rename_qdrant_collection.py --dry-run  # preview only
    uv run python scripts/rename_qdrant_collection.py --keep-legacy  # copy, don't drop
"""

import argparse
import asyncio
from typing import Any, cast

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams, VectorStruct

from app.core.config import Settings
from app.services.collection_naming import collection_name_for

SCROLL_BATCH_SIZE = 512


async def _migrate(settings: Settings, dry_run: bool, keep_legacy: bool) -> None:
    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=60,
        trust_env=False,
    )
    target = collection_name_for(settings.embedding_model)
    source = settings.qdrant_collection

    try:
        collections = await client.get_collections()
        names = {c.name for c in collections.collections}

        if source not in names:
            logger.warning("Legacy collection '{}' not found — nothing to migrate", source)
            if target in names:
                logger.info("Per-model collection '{}' already exists", target)
            return

        source_info = await client.get_collection(source)
        vectors_config = source_info.config.params.vectors
        if vectors_config is None:
            logger.error("Legacy collection '{}' has no vector config — aborting", source)
            return
        if isinstance(vectors_config, dict):
            first = next(iter(vectors_config.values()), None)
            dims = first.size if first else settings.embedding_dimensions
        else:
            dims = vectors_config.size

        logger.info("Source '{}': {} points, dim={}", source, source_info.points_count, dims)

        if target in names:
            target_info = await client.get_collection(target)
            logger.info("Target '{}' already exists ({} points) — will upsert into it", target, target_info.points_count)
        else:
            logger.info("Creating target collection '{}' (dim={}, COSINE)", target, dims)
            if not dry_run:
                await client.create_collection(
                    collection_name=target,
                    vectors_config=VectorParams(size=dims, distance=Distance.COSINE),
                )

        offset: Any = None
        migrated = 0
        while True:
            batch = await client.scroll(
                collection_name=source,
                offset=offset,
                limit=SCROLL_BATCH_SIZE,
                with_payload=True,
                with_vectors=True,
            )
            points, offset = batch
            if not points:
                break
            if not dry_run:
                batch_points = [PointStruct(id=p.id, vector=cast(VectorStruct, p.vector), payload=p.payload) for p in points if p.vector is not None]
                if batch_points:
                    await client.upsert(collection_name=target, points=batch_points)
            migrated += len(points)
            logger.info("Copied {} points...", migrated)
            if offset is None:
                break

        logger.info("Migrated {} points to '{}'", migrated, target)

        if dry_run:
            logger.info("DRY RUN — no changes made")
            return

        source_info = await client.get_collection(source)
        target_info = await client.get_collection(target)
        if source_info.points_count != target_info.points_count:
            logger.error(
                "Count mismatch: source={} target={} — keeping legacy collection, aborting drop",
                source_info.points_count,
                target_info.points_count,
            )
            return

        if keep_legacy:
            logger.info("Keeping legacy collection '{}' as requested", source)
        else:
            logger.info("Dropping legacy collection '{}'", source)
            await client.delete_collection(source)
            logger.info("Migration complete: {} -> {}", source, target)
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview the migration without changing anything")
    parser.add_argument("--keep-legacy", action="store_true", help="Copy into the new collection but do not drop the legacy one")
    args = parser.parse_args()

    settings = Settings()
    asyncio.run(_migrate(settings, dry_run=args.dry_run, keep_legacy=args.keep_legacy))


if __name__ == "__main__":
    main()
