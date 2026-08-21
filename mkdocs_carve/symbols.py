"""Build the symbol map a Carve page is rendered with.

Carve parses `:name:` as a symbol in its core - no extension needed - but what
a name renders as is a render option. A document that reaches the engine
without one renders `:smile:` as its own source text, which is what this
plugin did until now: it forwarded `extensions` and nothing else.

Two sources feed the map, in this order:

`emoji`
    An opt-in emoji table, off by default. The names are not bundled here -
    they are read from `pymdownx.emoji`, the same database this site's own
    Markdown pages resolve `:smile:` through (Material for MkDocs enables it
    by default). That matters more than shipping a list would: one source
    means a `:smile:` in `page.md` and a `:smile:` in `page.crv` on the same
    site cannot drift apart. When the site configures its own `emoji_index`
    in `markdown_extensions`, that index is used instead, so a project on
    Material's extended table gets the extended table on both page types.

`symbols`
    The site's own entries, layered on top so a project can override an emoji
    or add something that is not one at all.

SECURITY
--------

A mapped value is inserted as TRUSTED RAW output - the engine does not escape
it, exactly as it does not escape a `renderers` callback's return. That is
deliberate and it is the engine's documented contract:

    NEVER build a symbols map out of untrusted / user-supplied input.
    -- carve-lang's own ``to_html`` docstring

This module therefore never reads page content, front matter, or anything that
arrives with a request. Everything it returns is derived from `mkdocs.yml` (or
a JSON file whose path is written in `mkdocs.yml`) and from an emoji database
that ships as an installed package. The resolution happens once, in
``on_config``, before any page exists.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Mapping, Optional

__all__ = ["CDN", "MODES", "SymbolError", "emoji_map", "build"]

CDN = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@16.0.1/assets/svg/"
"""Fallback only - the value is read from `pymdownx.emoji` when it is there."""

MODES = ("none", "unicode", "twemoji")
"""The `emoji` setting's accepted values.

`none`
    No emoji table. `:smile:` stays literal unless `symbols` names it.

`unicode`
    The character itself. No network, no images, and it inherits the page's
    font - which on Linux is often no color emoji font at all.

`twemoji`
    The `<img class="twemoji">` element MkDocs emits for a Markdown page,
    pointing at the same CDN and carrying the same class, so the theme's
    sizing applies and the two page types look identical.
"""


class SymbolError(ValueError):
    """Raised when the symbol configuration cannot be used as written."""


def _cdn() -> str:
    try:
        from pymdownx.emoji import TWEMOJI_SVG_CDN
    except ImportError:  # pragma: no cover - only without pymdown-extensions
        return CDN
    return str(TWEMOJI_SVG_CDN)


def _default_index() -> Optional[Callable[..., Mapping[str, Any]]]:
    """`pymdownx.emoji.twemoji`, or ``None`` when it is not installed.

    `pymdown-extensions` is not a dependency of this plugin: rendering a Carve
    page does not need it, and a site that leaves `emoji` at `none` never asks
    for a name table at all. Material for MkDocs pulls it in, which is where
    almost every site that wants this feature gets it.
    """
    try:
        from pymdownx.emoji import twemoji
    except ImportError:
        return None
    return twemoji


@functools.lru_cache(maxsize=8)
def _database(
    index: Optional[Callable[..., Mapping[str, Any]]],
) -> tuple[Mapping[str, Any], Mapping[str, str]]:
    """The `(emoji, aliases)` pair an index factory produces.

    Cached on the factory itself, which is what keeps the 3840-entry table
    from being rebuilt for every page of a site.
    """
    factory = index if index is not None else _default_index()
    if factory is None:
        return {}, {}
    try:
        built = factory({}, {})
    except Exception as error:  # pragma: no cover - a database that will not load
        raise SymbolError(f"the emoji index could not be built: {error}") from error
    if not isinstance(built, Mapping):  # pragma: no cover - a hostile index
        raise SymbolError("the emoji index did not return a mapping")
    return built.get("emoji") or {}, built.get("aliases") or {}


def _character(unicode_points: str) -> str:
    return "".join(chr(int(point, 16)) for point in unicode_points.split("-"))


def emoji_map(
    mode: str,
    index: Optional[Callable[..., Mapping[str, Any]]] = None,
) -> dict[str, str]:
    """Return a Carve symbol map for ``mode``.

    Keys are bare names - Carve matches `:name:` and hands `name` to the map -
    while the emoji database is keyed by the colon form.

    Aliases are resolved rather than dropped. `pymdownx.emoji` renders `:+1:`
    on a Markdown page by following its alias to `:thumbsup:`; a Carve page
    that only knew the canonical names would render `:+1:` literally, which is
    the drift this module exists to prevent.

    Entries without a codepoint are icons rather than emoji (`:material-home:`
    and its ten thousand siblings), which resolve to an SVG file on disk. They
    are left out: reading ten thousand files to build one map costs more than
    the feature is worth, and an icon that stays literal is visibly missing
    rather than silently wrong.
    """
    if mode == "none":
        return {}
    if mode not in MODES:
        raise SymbolError(f"unknown emoji mode: {mode!r} (one of {', '.join(MODES)})")

    emoji, aliases = _database(index)
    if not emoji:
        raise SymbolError(
            f"emoji: {mode!r} needs an emoji database, and none is installed. "
            "Install `pymdown-extensions` (Material for MkDocs already depends "
            "on it), or set `emoji: none`."
        )

    cdn = _cdn()
    out: dict[str, str] = {}
    for shortname, entry in emoji.items():
        points = entry.get("unicode") if isinstance(entry, Mapping) else None
        if not points:
            continue
        out[shortname.strip(":")] = _render(mode, shortname, points, cdn)

    for alias, target in aliases.items():
        entry = emoji.get(target)
        points = entry.get("unicode") if isinstance(entry, Mapping) else None
        if not points:
            continue
        out.setdefault(alias.strip(":"), _render(mode, alias, points, cdn))

    return out


def _render(mode: str, shortname: str, points: str, cdn: str) -> str:
    character = _character(points)
    if mode == "unicode":
        return character
    return (
        f'<img alt="{character}" class="twemoji"'
        f' src="{cdn}{points}.svg" title="{shortname}" />'
    )


def build(
    mode: str,
    extra: Optional[Mapping[str, str]] = None,
    index: Optional[Callable[..., Mapping[str, Any]]] = None,
) -> Optional[dict[str, str]]:
    """The map Carve is called with: the emoji table, then the site's own.

    ``None`` rather than an empty map when there is nothing to pass, so the
    engine keeps its own default behavior instead of being told "no symbols".
    """
    combined = dict(emoji_map(mode, index))
    if extra:
        combined.update(extra)
    return combined or None
