import pathlib
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.scrapers.exceptions import ScraperAuthError


class BaseScraper(ABC):
    name: str = ""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @abstractmethod
    async def run(self, **kwargs: object) -> dict[str, Any]: ...

    async def _resolve_header(self, kwargs: dict[str, object]) -> tuple[str, str]:
        """Resolve the raw header value for this scraper.

        Priority: explicit ``cookie``/``cookie_file`` kwargs → the DB row in
        ``scraper_headers`` for ``self.name``. Returns ``(raw, source)`` where
        source is ``"explicit"``, ``"db"`` or ``"none"``.
        """
        raw = str(kwargs.get("cookie", "") or "")
        if not raw:
            cookie_file = str(kwargs.get("cookie_file", "") or "")
            if cookie_file:
                try:
                    raw = pathlib.Path(cookie_file).read_text().strip()
                except OSError:
                    raw = ""
            if raw:
                return raw, "explicit"
        if raw:
            return raw, "explicit"

        if self.db is None:
            return "", "none"

        from app.repositories.scraper_header import ScraperHeaderRepository

        repo = ScraperHeaderRepository(self.db)
        row = await repo.get_by_name(self.name)
        if row is not None and row.header:
            return row.header, "db"
        return "", "none"

    def _require_header(self, raw: str, source: str) -> None:
        """Raise a clear error when the scraper has no usable header."""
        if not raw or source == "none":
            raise ScraperAuthError(f"No header configured for scraper '{self.name}' — set it in the admin panel (Admin → Settings → Scrapers)")
