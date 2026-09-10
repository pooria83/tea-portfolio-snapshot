import hashlib
import re

MAX_COLLECTION_NAME_LENGTH = 200


def collection_slug(model_name: str) -> str:
    """Normalize a model name into a Qdrant-friendly slug segment.

    Lowercases, replaces runs of non-alphanumeric characters with a single
    dash, and trims leading/trailing dashes.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", model_name.lower()).strip("-")
    return slug


def collection_name_for(model_name: str) -> str:
    """Build the per-model Qdrant collection name for an embedding model.

    Returns ``products-{slug}`` when the slug is short enough, otherwise falls
    back to ``products-{sha1(model_name)[:12]}`` to stay within Qdrant's
    255-character collection name limit.
    """
    slug = collection_slug(model_name)
    if slug and len(f"products-{slug}") <= MAX_COLLECTION_NAME_LENGTH:
        return f"products-{slug}"
    digest = hashlib.sha1(model_name.encode("utf-8")).hexdigest()[:12]
    return f"products-{digest}"
