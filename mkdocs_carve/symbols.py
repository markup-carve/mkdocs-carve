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
import inspect
import logging
from typing import Any, Callable, Mapping, Optional

__all__ = ["CDN", "MODES", "SymbolError", "emoji_map", "build"]

log = logging.getLogger(f"mkdocs.plugins.{__name__}")

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


@functools.lru_cache(maxsize=1)
def _markdown() -> Any:
    """A Markdown instance to hand the index factory as its second argument.

    `pymdownx` calls ``index(self.options, self.md)``, so an index is entitled
    to touch that argument. There is no Markdown instance in a Carve render -
    the whole point of a `.crv` page is that Markdown never runs - so a bare
    one stands in. `markdown` is a hard dependency of MkDocs, so it is always
    importable; an empty mapping here used to be a `TypeError` waiting for the
    first index that looked at it.
    """
    try:
        import markdown
    except ImportError:  # pragma: no cover - markdown ships with mkdocs
        return None
    return markdown.Markdown()


def _invoke(
    factory: Callable[..., Mapping[str, Any]],
    options: Optional[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, str]]:
    try:
        # A zero-argument factory is `pymdownx`'s deprecated legacy form, and
        # it still calls those without arguments rather than failing.
        arity = len(inspect.getfullargspec(factory).args)
        built = factory(dict(options or {}), _markdown()) if arity else factory()
    except Exception as error:
        raise SymbolError(f"the emoji index could not be built: {error}") from error
    if not isinstance(built, Mapping):
        raise SymbolError("the emoji index did not return a mapping")
    return built.get("emoji") or {}, built.get("aliases") or {}


def _database(
    index: Optional[Callable[..., Mapping[str, Any]]],
    options: Optional[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, str]]:
    """The `(emoji, aliases)` pair an index factory produces.

    ``options`` is the `options` sub-key of the site's `pymdownx.emoji`
    configuration, which is exactly what `pymdownx` itself hands the factory
    (`EmojiPattern._set_index` calls ``index(self.options, self.md)``).
    Dropping it would silently build a different table than the Markdown pages
    on the same site get - Material's index reads its custom-icon paths from
    there - which is the one thing this module exists to prevent.

    A SITE-CONFIGURED index that will not build falls back to the stock table
    with a warning rather than failing the build. The setting belongs to
    another extension and was not written for this plugin, so an index that
    depends on Markdown state a Carve render does not have should cost the
    site its extra names, not its build. `mkdocs build --strict` turns the
    warning into the hard failure for sites that would rather stop.
    """
    factory = index if index is not None else _default_index()
    if factory is None:
        return {}, {}
    try:
        return _invoke(factory, options)
    except SymbolError as error:
        fallback = _default_index()
        if index is None or fallback is None or fallback is factory:
            raise
        log.warning(
            "carve: the site's pymdownx.emoji index could not be used (%s); "
            "falling back to the stock emoji table, so a Carve page may "
            "resolve fewer names than a Markdown page on this site",
            error,
        )
        return _invoke(fallback, None)


_CACHE: dict[Any, dict[str, str]] = {}
"""Resolved maps, keyed by what produced them.

Built once per process rather than per page: the stock table is 3840 entries
before aliases. The key has to survive a `dict` of index options, so it is
frozen below; anything that will not freeze skips the cache rather than
raising, because a slow build beats a broken one.
"""

_CACHE_LIMIT = 8


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted(((k, _freeze(v)) for k, v in value.items()), key=repr))
    if isinstance(value, (list, tuple, set)):
        return tuple(_freeze(v) for v in value)
    return value


def _character(unicode_points: str) -> str:
    return "".join(chr(int(point, 16)) for point in unicode_points.split("-"))


def emoji_map(
    mode: str,
    index: Optional[Callable[..., Mapping[str, Any]]] = None,
    options: Optional[Mapping[str, Any]] = None,
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

    key: Any = (mode, index, _freeze(options))
    try:
        hash(key)
    except TypeError:  # pragma: no cover - only an unfreezable option value
        key = None
    if key is not None and key in _CACHE:
        # A copy, so a caller that edits what it got back does not edit what
        # the next page is rendered with.
        return dict(_CACHE[key])

    emoji, aliases = _database(index, options)
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

    if key is not None:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.clear()
        _CACHE[key] = dict(out)
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
    options: Optional[Mapping[str, Any]] = None,
) -> Optional[dict[str, str]]:
    """The map Carve is called with: the emoji table, then the site's own.

    ``None`` rather than an empty map when there is nothing to pass, so the
    engine keeps its own default behavior instead of being told "no symbols".
    """
    combined = dict(emoji_map(mode, index, options))
    if extra:
        combined.update(extra)
    return combined or None
