"""Whether the engine this plugin RESOLVES carries the 0.1.3 security fix.

The dependency is a floor with no upper bound, so what gets installed is
whatever PyPI serves as latest. That is not a detail this repository can read
off its own manifest: `pyproject.toml` looks current either way, and every
other test here passes against a vulnerable engine exactly as well as against a
patched one - 25 of 25 did, which is what prompted this file.

The defect is Carve 0.1.3's: a list-valued URL attribute was probed only on its
FIRST entry, so a payload in the second one was never sanitized.

This began life as an ``xfail(strict=True)``, quiet while PyPI's newest
carve-lang was vulnerable and failing the day a patched one appeared. That day
came: carve-lang 0.1.1 sanitizes the case, the floor in `pyproject.toml` moved
to it, and the marker is gone. The assertion stays, because the floor is still
open at the top and a future engine could regress it.
"""

from __future__ import annotations

import carve

PAYLOAD = '![x](safe.png){srcset="safe.png 1x, javascript:alert(1) 2x"}\n'


def test_the_resolved_engine_sanitizes_list_valued_url_attributes():
    html = carve.to_html(PAYLOAD)
    assert "javascript:" not in html.lower(), (
        f"the installed carve-lang ({_version()}) emitted an unsanitized "
        f"javascript: URL in a list-valued attribute: {html.strip()}"
    )


def _version():
    try:
        from importlib.metadata import version

        return version("carve-lang")
    except Exception:  # pragma: no cover - only reached on a broken install
        return "unknown"


def test_the_payload_still_reaches_the_engine():
    """The probe above is only evidence if the engine actually renders it.

    Without this, a carve-lang that raised on the input - or one whose
    ``to_html`` returned an empty string - would satisfy the assertion above by
    producing nothing, and the xfail bookkeeping would report a state that was
    never measured.
    """
    html = carve.to_html(PAYLOAD)
    assert "<img" in html, f"the engine did not render an image at all: {html!r}"
    assert "safe.png" in html, f"the engine dropped the source URL: {html!r}"
