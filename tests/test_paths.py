import sys
from pathlib import Path

from src import paths


def test_resources_come_from_the_checkout_when_run_from_source():
    assert paths.resource("data", "lisbon.json").is_file()
    assert paths.resource("docs", "icon.png").is_file()


def test_resources_come_from_the_bundle_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.root() == tmp_path
    assert paths.resource("data", "lisbon.json") == Path(tmp_path, "data", "lisbon.json")
