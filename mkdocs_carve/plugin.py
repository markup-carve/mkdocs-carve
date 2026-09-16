"""MkDocs plugin that renders Carve (`.crv`) source files as pages.

Carve is a lightweight markup language. This plugin teaches MkDocs to treat
`.crv` files as documentation pages and converts them to HTML via
the `carve` engine (python-carve), so the active MkDocs theme wraps the output
exactly like a normal Markdown page.

Design notes
------------

* MkDocs natively decides a page's destination path and URL from the source
  file's *extension* (only ``.md`` and friends count as documentation pages)
  and from ``use_directory_urls``. Rather than hand-roll those rules (the
  proof-of-concept did, and it was brittle), this plugin reuses MkDocs' own
  algorithm: it marks each Carve ``File`` as a documentation page and recomputes
  ``dest_uri``/``url`` with the same posixpath logic MkDocs applies to Markdown.
  That gives correct output for ``index`` pages, nested folders, ``README``
  files, and both ``use_directory_urls`` modes for free.

* The Carve ``File`` keeps its original ``.crv`` ``src_uri``. Nav
  entries in ``mkdocs.yml`` are resolved by ``src_uri``, so a ``nav`` line such
  as ``- Guide: guide/intro.crv`` keeps working without translation. Keeping a
  single canonical key per file also avoids the double-build that an aliased
  extra key in the ``Files`` collection would cause.

* Conversion happens in ``on_page_markdown``. MkDocs' Markdown step passes raw
  HTML through untouched, so returning the converted Carve fragment there lets
  the theme template wrap it. This is simpler than synthesizing a custom page
  and renders identically through every theme.

* The symbol map that turns `:smile:` into an emoji is resolved once, in
  ``on_config``, and never per page. That is a cost decision - the emoji table
  has thousands of entries - but it is also the security boundary: a map
  built before any page exists cannot have been influenced by page content.
  See ``mkdocs_carve.symbols`` for why that matters (the values are emitted
  RAW).

* Include expansion is the engine's, never this plugin's. ``include_root`` is
  handed to ``carve.render_with_includes`` as the site wrote it, so the
  resolver's own refusal of a relative root is what fires. Only the default,
  derived from ``docs_dir``, is absolutized here.
"""

from __future__ import annotations

import json
import os
import posixpath
from typing import Any, Dict, Optional

import carve
from mkdocs.config import config_options
from mkdocs.config.base import ValidationError
from mkdocs.plugins import BasePlugin, get_plugin_logger

from mkdocs_carve import symbols as symbols_module

log = get_plugin_logger(__name__)

#: Source extensions this plugin claims as Carve documentation pages.
CARVE_SUFFIXES = (".crv",)

#: Extensions enabled by default. Permalinks on headings are broadly useful for
#: documentation sites and are the carve analog of MkDocs' Markdown ``toc``
#: permalinks. Override via the plugin's ``extensions`` config key.
DEFAULT_EXTENSIONS = ["heading_permalinks"]


def convert_carve(
    source: str,
    extensions: Optional[list] = None,
    symbols: Optional[Dict[str, str]] = None,
) -> str:
    """Convert a Carve source string into an HTML fragment.

    ``extensions`` is the list of carve extension names to enable (passed
    straight through to ``carve.to_html``). ``None`` means the core renderer.

    ``symbols`` maps a `:name:` symbol to what it renders as. ``None`` leaves
    the engine's own default behavior, under which every `:name:` stays
    literal. Values are emitted RAW by the engine and must therefore come from
    the site's own configuration - see ``mkdocs_carve.symbols``.
    """
    return carve.to_html(source, extensions=extensions, symbols=symbols)


def convert_carve_with_includes(
    source: str,
    include_root: str,
    source_path: str,
    extensions: Optional[list] = None,
    symbols: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Convert Carve source with `{{ path }}` includes expanded from disk.

    ``include_root`` reaches the engine unchanged. ``source_path`` is the
    document's identity relative to that root; every path the engine reports
    back is relative to it too, so a message shown to a reader carries no host
    directory layout.
    """
    return carve.render_with_includes(
        source,
        include_root,
        target="html",
        extensions=extensions,
        symbols=symbols,
        source_path=source_path,
    )


def _is_carve_path(src_uri: str) -> bool:
    return src_uri.endswith(CARVE_SUFFIXES)


def _carve_dest_uri(file: Any, use_directory_urls: bool) -> str:
    """Compute the destination URI for a Carve file the way MkDocs does for `.md`.

    Mirrors ``mkdocs.structure.files.File._get_dest_path``: the page name
    (extension-stripped stem) plus ``use_directory_urls`` fully determine the
    layout, independent of the source extension.
    """
    parent, _ = posixpath.split(file.src_uri)
    name = file.name  # stem without extension; "README" already maps to "index"
    if not use_directory_urls or name == "index":
        # index.crv => index.html ; foo.crv => foo.html
        return posixpath.join(parent, name + ".html")
    # foo.crv => foo/index.html
    return posixpath.join(parent, name, "index.html")


def _carve_url(dest_uri: str, use_directory_urls: bool) -> str:
    """Compute the public URL from a destination URI, matching MkDocs' rule."""
    dirname, filename = posixpath.split(dest_uri)
    if use_directory_urls and filename == "index.html":
        return (dirname or ".") + "/"
    return dest_uri


class CarvePlugin(BasePlugin):
    """Render `.crv` pages through the carve engine."""

    config_scheme = (
        (
            "extensions",
            config_options.ListOfItems(
                config_options.Type(str), default=list(DEFAULT_EXTENSIONS)
            ),
        ),
        # Off by default: a bundled table would decide for the site what
        # `:smile:` means, and a site that has not asked for emoji should get
        # the engine's own behavior unchanged.
        ("emoji", config_options.Choice(symbols_module.MODES, default="none")),
        # Either the mapping itself, or a path to a JSON file holding one. The
        # file form exists because a project's own symbols are usually a long
        # list, and a long list in the middle of `mkdocs.yml` hides everything
        # after it.
        ("symbols", config_options.Type((dict, str), default=None)),
        # Off by default: expansion reads files a string conversion never
        # touches, so a site opts into it rather than discovering it.
        ("includes", config_options.Type(bool, default=False)),
        # An explicit containment root. Left unset, the root is `docs_dir`.
        ("include_root", config_options.Type(str, default=None)),
    )

    #: Resolved in ``on_config`` and reused for every page. ``None`` means
    #: "pass nothing", which is not the same as an empty map.
    _symbols: Optional[Dict[str, str]] = None

    #: The containment root, or ``None`` when expansion is off.
    _include_root: Optional[str] = None

    def on_config(self, config):
        """Resolve the symbol map once, before any page is rendered.

        Doing this here rather than per page is what makes the trust boundary
        checkable: the only inputs are `mkdocs.yml`, a JSON file it names, and
        an installed emoji database. No page has been read yet, so no page can
        have contributed a value - which matters because the engine emits
        these values RAW.
        """
        extra = self._read_symbols(self.config.get("symbols"), config)
        index, options = self._site_emoji_index(config)
        try:
            self._symbols = symbols_module.build(
                self.config["emoji"], extra, index, options
            )
        except symbols_module.SymbolError as error:
            raise ValidationError(str(error)) from error
        self._include_root = self._resolve_include_root(config)
        return config

    def _resolve_include_root(self, config: Any) -> Optional[str]:
        """The containment root for this build, or ``None`` when includes are off.

        A configured value is handed to the engine exactly as written. The
        resolver refuses a relative root, and that refusal is what keeps
        containment off the process working directory - absolutizing here would
        mean it never fires. The derived default has no such history: it is
        this plugin's own value, so it is absolutized.
        """
        if not self.config["includes"]:
            return None
        if not hasattr(carve, "render_with_includes"):
            raise ValidationError(
                "includes: the installed carve-lang exposes no "
                "render_with_includes; upgrade the engine or set includes: false"
            )
        configured = self.config["include_root"]
        root = configured if configured else os.path.abspath(config["docs_dir"])
        try:
            carve.render_with_includes("", root)
        except ValueError as error:
            raise ValidationError(f"include_root: {error}") from error
        return root

    @staticmethod
    def _site_emoji_index(config: Any) -> tuple[Optional[Any], Optional[dict]]:
        """The emoji index this site's MARKDOWN pages use, when it set one.

        Material for MkDocs points `pymdownx.emoji` at its own extended index,
        so a site on Material resolves more names in a `.md` page than the
        stock table holds. Reading the same setting here is the whole point of
        not bundling a table: the two page types resolve `:name:` through one
        database or they drift.

        The `options` sub-key comes along with it, because that is what
        `pymdownx` passes the factory - Material reads its custom-icon paths
        from there, so an index called without them builds a different table
        than the Markdown pages get.

        Anything unexpected in either setting falls back rather than failing
        the build: they belong to another extension, and this plugin is not
        the right place to validate them.
        """
        try:
            emoji_config = config["mdx_configs"]["pymdownx.emoji"]
            configured = emoji_config["emoji_index"]
        except (KeyError, TypeError):
            return None, None
        if not callable(configured):
            return None, None
        options = emoji_config.get("options") if hasattr(emoji_config, "get") else None
        return configured, options if isinstance(options, dict) else None

    @staticmethod
    def _read_symbols(raw: Any, config: Any) -> Optional[Dict[str, str]]:
        """The `symbols` setting, with the file form read from disk."""
        if raw is None or raw == "" or raw == {}:
            return None

        if isinstance(raw, str):
            # Relative to `mkdocs.yml`, the file the path was written in -
            # never to `docs_dir`, so a symbol map can never be mistaken for
            # page content and shipped into the built site.
            #
            # A config assembled in memory has no file, and then the working
            # directory IS the base. Deriving it from `dirname(abspath("."))`
            # would land one directory ABOVE the working directory instead.
            config_file = config.get("config_file_path") if hasattr(config, "get") else None
            base = os.path.dirname(os.path.abspath(config_file)) if config_file else os.getcwd()
            path = os.path.join(base, raw)
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
            except OSError as error:
                raise ValidationError(f"symbols: {raw}: {error}") from error
            except json.JSONDecodeError as error:
                raise ValidationError(f"symbols: {raw}: {error}") from error
        else:
            data = raw

        if not isinstance(data, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in data.items()
        ):
            where = f"symbols: {raw}" if isinstance(raw, str) else "symbols"
            raise ValidationError(f"{where}: must map a name to a string")
        return dict(data)

    def on_files(self, files, *, config):
        """Promote Carve source files to documentation pages.

        Each `.crv` ``File`` is marked as a documentation page and
        has its ``dest_uri`` / ``url`` recomputed using MkDocs' own Markdown
        layout rules, so it slots into the build like any `.md` page.
        """
        use_directory_urls = config["use_directory_urls"]
        for file in files:
            src_uri = file.src_uri or ""
            if not _is_carve_path(src_uri):
                continue

            # MkDocs only treats Markdown extensions as documentation pages.
            # Force this Carve file to count as one.
            file.is_documentation_page = lambda: True  # type: ignore[method-assign]

            dest_uri = _carve_dest_uri(file, use_directory_urls)
            # Setting dest_uri also refreshes abs_dest_path via MkDocs internals.
            file.dest_uri = dest_uri
            file.abs_dest_path = posixpath.normpath(
                posixpath.join(file.dest_dir, dest_uri)
            )
            file.url = _carve_url(dest_uri, use_directory_urls)
        return files

    def on_page_markdown(self, markdown, *, page, config, files):
        """Convert Carve source to HTML before the Markdown step runs.

        Returned HTML is passed through untouched by MkDocs' Markdown renderer,
        so the theme template wraps it like normal page content.
        """
        src_uri = getattr(page.file, "src_uri", "") or ""
        if not _is_carve_path(src_uri):
            return markdown
        extensions = self.config["extensions"] or None
        abs_src_path = getattr(page.file, "abs_src_path", None)
        if not self._include_root or not abs_src_path:
            return convert_carve(markdown, extensions=extensions, symbols=self._symbols)

        result = convert_carve_with_includes(
            markdown,
            self._include_root,
            os.path.relpath(abs_src_path, self._include_root),
            extensions=extensions,
            symbols=self._symbols,
        )
        self._report(result, src_uri)
        return result["output"]

    def _report(self, result: Dict[str, Any], src_uri: str) -> None:
        """Log what expansion degraded, located on the page that asked for it."""
        for warning in result["warnings"]:
            origin = warning.get("file")
            where = src_uri if not origin or origin == src_uri else f"{src_uri} ({origin})"
            log.warning("%s: %s: %s", where, warning["rule"], warning["message"])
        suppressed = result["suppressed_warnings"]
        if suppressed:
            log.warning("%s: %d further include warnings suppressed", src_uri, suppressed)
        # The engine reports a containment denial and a missing file as one
        # warning so a page cannot probe the filesystem (spec I7). The class
        # that was collapsed is on the dependency, for the build's own log.
        for dependency in result["dependencies"]:
            if dependency["denial"]:
                log.info(
                    "%s: include %s: %s", src_uri, dependency["id"], dependency["denial"]
                )

    def on_serve(self, server, *, config, builder):
        """Rebuild when anything under the containment root changes.

        Watching the root rather than the targets a build happened to touch is
        what containment buys: a target that does not exist yet has no path to
        watch, and an unresolved dependency reports the directive as written
        rather than a path relative to the root, so it cannot be joined back
        onto one. Every target, present or not, lies under the root.
        """
        if self._include_root:
            server.watch(self._include_root)
        return server
