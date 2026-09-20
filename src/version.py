"""The one place the version is written down.

The panel shows it, the macOS app carries it in its Info.plist, and the
release workflow takes the notes for it out of CHANGELOG.md, so a release
that forgets the changelog entry ships with an empty body. A test keeps the
two in step.
"""

VERSION = "1.3.0"
