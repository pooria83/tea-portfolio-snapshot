from __future__ import annotations

import json
import os

from app.services.config_manager import ConfigManager


class TestConfigManager:
    def test_init_without_file(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "nonexistent.json")
        cm = ConfigManager(path)
        assert cm.has_config() is False
        assert cm.get("key") == ""

    def test_init_with_existing_file(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "config.json")
        with open(path, "w") as f:
            json.dump({"foo": "bar"}, f)
        cm = ConfigManager(path)
        assert cm.has_config() is True
        assert cm.get("foo") == "bar"

    def test_get_with_default(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "empty.json")
        cm = ConfigManager(path)
        assert cm.get("missing", "fallback") == "fallback"

    def test_set_and_persist(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "persist.json")
        cm = ConfigManager(path)
        cm.set("color", "blue")
        assert cm.get("color") == "blue"

        cm2 = ConfigManager(path)
        assert cm2.get("color") == "blue"

    def test_reload_clears_and_rerereads(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "reload.json")
        cm = ConfigManager(path)
        cm.set("a", "1")

        with open(path, "w") as f:
            json.dump({"b": "2"}, f)

        cm.reload()
        assert cm.get("a") == ""
        assert cm.get("b") == "2"

    def test_has_config_after_set(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "has_config.json")
        cm = ConfigManager(path)
        assert cm.has_config() is False
        cm.set("x", "y")
        assert cm.has_config() is True

    def test_corrupted_file_does_not_crash(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "bad.json")
        with open(path, "w") as f:
            f.write("{invalid json")
        cm = ConfigManager(path)
        assert cm.has_config() is False

    def test_save_to_nonexistent_directory_creates_it(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "sub", "nested", "config.json")
        cm = ConfigManager(path)
        cm.set("key", "val")
        assert os.path.exists(path)
        with open(path) as f:
            assert json.load(f) == {"key": "val"}

    def test_atomic_save_leaves_no_temp_files(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "atomic.json")
        cm = ConfigManager(path)
        for i in range(3):
            cm.set("key", f"val{i}")
        leftovers = [n for n in os.listdir(tmp_path) if n != "atomic.json"]
        assert leftovers == []
        with open(path) as f:
            assert json.load(f) == {"key": "val2"}

    def test_load_ignores_non_string_values(self, tmp_path: str) -> None:
        path = os.path.join(tmp_path, "mixed.json")
        with open(path, "w") as f:
            json.dump({"good": "value", "bad": {"nested": 1}, "num": 123}, f)
        cm = ConfigManager(path)
        assert cm.get("good") == "value"
        assert cm.get("bad") == ""
        assert cm.get("num") == ""
