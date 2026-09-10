import json
import os
import tempfile
from contextlib import suppress

from loguru import logger


class ConfigManager:
    def __init__(self, path: str) -> None:
        self._path = path
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path) as f:
                    raw = json.load(f)
                self._data = {k: v for k, v in raw.items() if isinstance(v, str)}
                logger.info("Loaded runtime config from {}", self._path)
            else:
                logger.info("No runtime config file at {} — using defaults", self._path)
        except Exception:
            logger.opt(exception=True).warning("Failed to load runtime config from {}", self._path)

    def _save(self) -> None:
        try:
            directory = os.path.dirname(self._path) or "."
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".config-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self._data, f)
                os.replace(tmp_path, self._path)
            except Exception:
                with suppress(OSError):
                    os.unlink(tmp_path)
                raise
            logger.info("Saved runtime config to {}", self._path)
        except Exception as exc:
            logger.warning("Failed to save runtime config to {}: {}", self._path, exc)

    def reload(self) -> None:
        self._data.clear()
        self._load()

    def has_config(self) -> bool:
        return bool(self._data)

    def get(self, key: str, default: str = "") -> str:
        value = self._data.get(key, default)
        return value if isinstance(value, str) else default

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._save()
