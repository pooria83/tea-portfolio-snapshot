"""Shared scraper exceptions.

Kept in the top-level scrapers package so base classes (``BaseScraper``) can
raise them without depending on a specific scraper implementation.
"""


class ScraperError(Exception):
    pass


class ScraperAuthError(ScraperError):
    def __init__(self, message: str = "Authentication failed — cookie/token expired or missing") -> None:
        self.message = message
        super().__init__(self.message)


class ScraperHTTPError(ScraperError):
    def __init__(self, status_code: int, url: str, body: str = "") -> None:
        self.status_code = status_code
        self.url = url
        self.body = body
        super().__init__(f"HTTP {status_code} for {url}: {body[:200]}")


class ScraperParseError(ScraperError):
    def __init__(self, message: str, source: str = "") -> None:
        self.source = source
        super().__init__(f"Parse error{' at ' + source if source else ''}: {message}")
