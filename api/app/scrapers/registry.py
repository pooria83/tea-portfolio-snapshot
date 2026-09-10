from collections.abc import Callable

from app.scrapers.base import BaseScraper

_scrapers: dict[str, type[BaseScraper]] = {}


def register_scraper(name: str) -> Callable[[type[BaseScraper]], type[BaseScraper]]:
    def decorator(cls: type[BaseScraper]) -> type[BaseScraper]:
        cls.name = name
        _scrapers[name] = cls
        return cls

    return decorator


def get_scraper(name: str) -> type[BaseScraper]:
    scraper = _scrapers.get(name)
    if scraper is None:
        msg = f"Unknown scraper: {name}. Available: {list(_scrapers.keys())}"
        raise ValueError(msg)
    return scraper
