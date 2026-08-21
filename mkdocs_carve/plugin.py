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
"""

from __future__ import annotations

import json
import os
import posixpath
from typing import Any, Dict, Optional

import carve
from mkdocs.config import config_options
from mkdocs.config.base import ValidationError
from mkdocs.plugins import BasePlugin

from mkdocs_carve import symbols as symbols_module

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
    )

    #: Resolved in ``on_config`` and reused for every page. ``None`` means
    #: "pass nothing", which is not the same as an empty map.
    _symbols: Optional[Dict[str, str]] = None

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
        return config

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
        return convert_carve(markdown, extensions=extensions, symbols=self._symbols)
