"""The version, the changelog and the release notes have to agree.

The release workflow cuts the notes for a tag out of CHANGELOG.md by
matching the heading. A tag with no entry publishes a release with an empty
body, and nobody notices until it is out.
"""

import pathlib
import re

from src.version import VERSION

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def notes_for(version: str) -> str:
    """What the release workflow's awk would pull out for this version."""
    kept, on = [], False
    for line in CHANGELOG.splitlines():
        if line.startswith("## "):
            on = line.startswith(f"## {version}")
            continue
        if on:
            kept.append(line)
    return "\n".join(kept).strip()


def test_the_version_is_a_release_number():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION


def test_the_changelog_leads_with_this_version():
    headings = [line for line in CHANGELOG.splitlines() if line.startswith("## ")]
    assert headings, "no versions in the changelog at all"
    assert headings[0].startswith(f"## {VERSION} "), headings[0]


def test_this_version_has_release_notes():
    assert len(notes_for(VERSION)) > 200, "a release with an empty body helps nobody"


def test_the_app_is_stamped_with_the_version():
    build = (ROOT / "tools" / "build_app.sh").read_text()
    assert "src/version.py" in build, "the app should carry the same version, not its own"
