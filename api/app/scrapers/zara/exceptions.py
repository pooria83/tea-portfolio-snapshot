"""Zara scraper exceptions.

Re-exports the shared scraper exceptions for backwards compatibility with
imports of ``app.scrapers.zara.exceptions``.
"""

from app.scrapers.exceptions import ScraperAuthError, ScraperError, ScraperHTTPError, ScraperParseError

__all__ = ["ScraperAuthError", "ScraperError", "ScraperHTTPError", "ScraperParseError"]
