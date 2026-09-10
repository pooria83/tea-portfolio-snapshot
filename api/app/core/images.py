"""Public helpers for image URL handling."""

from app.core.config import settings


def normalize_image_url(url: str | None) -> str | None:
    """Resolve a stored image path (or legacy dev host) to a full public URL."""
    if not url:
        return url
    if url.startswith("https://portfolio.example.invalid/"):
        return f"{settings.minio_public_url}/{url.removeprefix('https://portfolio.example.invalid/')}"
    if not url.startswith("http"):
        return f"{settings.minio_public_url}/{url}"
    return url
