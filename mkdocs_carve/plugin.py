"""MkDocs plugin that renders Carve (`.crv` / `.carve`) source files as pages.

Carve is a lightweight markup language. This plugin teaches MkDocs to treat
`.crv` and `.carve` files as documentation pages and converts them to HTML via
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

* The Carve ``File`` keeps its original ``.crv`` / ``.carve`` ``src_uri``. Nav
  entries in ``mkdocs.yml`` are resolved by ``src_uri``, so a ``nav`` line such
  as ``- Guide: guide/intro.crv`` keeps working without translation. Keeping a
  single canonical key per file also avoids the double-build that an aliased
  extra key in the ``Files`` collection would cause.

* Conversion happens in ``on_page_markdown``. MkDocs' Markdown step passes raw
  HTML through untouched, so returning the converted Carve fragment there lets
  the theme template wrap it. This is simpler than synthesizing a custom page
  and renders identically through every theme.
"""

from __future__ import annotations

import posixpath
from typing import Any, Optional

import carve
from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin

#: Source extensions this plugin claims as Carve documentation pages.
CARVE_SUFFIXES = (".crv", ".carve")

#: Extensions enabled by default. Permalinks on headings are broadly useful for
#: documentation sites and are the carve analog of MkDocs' Markdown ``toc``
#: permalinks. Override via the plugin's ``extensions`` config key.
DEFAULT_EXTENSIONS = ["heading_permalinks"]


def convert_carve(source: str, extensions: Optional[list] = None) -> str:
    """Convert a Carve source string into an HTML fragment.

    ``extensions`` is the list of carve extension names to enable (passed
    straight through to ``carve.to_html``). ``None`` means the core renderer.
    """
    return carve.to_html(source, extensions=extensions)


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
    """Render `.crv` / `.carve` pages through the carve engine."""

    config_scheme = (
        (
            "extensions",
            config_options.ListOfItems(
                config_options.Type(str), default=list(DEFAULT_EXTENSIONS)
            ),
        ),
    )

    def on_files(self, files, *, config):
        """Promote Carve source files to documentation pages.

        Each `.crv` / `.carve` ``File`` is marked as a documentation page and
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
        return convert_carve(markdown, extensions=extensions)
