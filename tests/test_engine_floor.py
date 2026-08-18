"""Whether the engine this plugin RESOLVES carries the 0.1.3 security fix.

The dependency is ``carve-lang>=0.1.0``, an open floor, so what gets installed
is whatever PyPI serves as latest. That is not a detail this repository can
read off its own manifest: `pyproject.toml` looks current either way, and every
other test here passes against a vulnerable engine exactly as well as against a
patched one - 25 of 25 did, which is what prompted this file.

The defect is Carve 0.1.3's: a list-valued URL attribute was probed only on its
FIRST entry, so a payload in the second one was never sanitized.

This is an ``xfail(strict=True)`` rather than a plain assertion, and the
strictness is the entire point:

    while PyPI's newest carve-lang is vulnerable   -> xfail, the suite stays green
    the day a patched carve-lang is published      -> XPASS, and strict turns
                                                      that into a FAILURE

So the check does not hold this repository red for a fix it cannot make, and it
cannot go quiet either: it reports the moment the floor can be raised, which is
the moment this plugin can be released. Raise the floor in `pyproject.toml`,
then delete the marker below and keep the assertion.
"""

from __future__ import annotations

import pytest

import carve

PAYLOAD = '![x](safe.png){srcset="safe.png 1x, javascript:alert(1) 2x"}\n'


@pytest.mark.xfail(
    strict=True,
    reason=(
        "carve-lang on PyPI is 0.1.0, published 2026-08-12, which predates the "
        "Carve 0.1.3 security release. When this XPASSes, a patched carve-lang "
        "is available: raise the floor in pyproject.toml and drop this marker."
    ),
)
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
