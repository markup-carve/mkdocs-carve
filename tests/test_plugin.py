"""Unit tests for the mkdocs-carve plugin.

These exercise the plugin's logic directly (file registration, path rewriting
for the tricky cases, extension passthrough, and `.md` coexistence) without
running a full `mkdocs build`. A separate end-to-end build is covered by
``test_build.py``.
"""

from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

import pytest
from mkdocs.structure.files import File, Files

from mkdocs_carve.plugin import (
    CARVE_SUFFIXES,
    CarvePlugin,
    convert_carve,
)


def _make_file(src_uri, docs_dir, site_dir, use_directory_urls, content="# H\n\n*b*"):
    """Create a real File backed by an on-disk source so content reads work."""
    abs_src = os.path.join(docs_dir, src_uri)
    os.makedirs(os.path.dirname(abs_src), exist_ok=True)
    with open(abs_src, "w", encoding="utf-8") as fh:
        fh.write(content)
    return File(src_uri, docs_dir, site_dir, use_directory_urls=use_directory_urls)


def _run_on_files(files_list, use_directory_urls, site_dir, plugin=None):
    plugin = plugin or CarvePlugin()
    plugin.load_config({})  # apply config_scheme defaults
    config = {"use_directory_urls": use_directory_urls, "site_dir": site_dir}
    return plugin.on_files(Files(files_list), config=config)


@pytest.fixture()
def dirs():
    docs = tempfile.mkdtemp(prefix="carve-docs-")
    site = tempfile.mkdtemp(prefix="carve-site-")
    yield docs, site


# --- 1. Carve files become documentation pages -----------------------------


def test_crv_file_promoted_to_documentation_page(dirs):
    docs, site = dirs
    f = _make_file("index.crv", docs, site, use_directory_urls=True)
    assert f.is_documentation_page() is False  # MkDocs default: not Markdown
    _run_on_files([f], True, site)
    assert f.is_documentation_page() is True


def test_md_file_left_untouched(dirs):
    docs, site = dirs
    md = _make_file("page.md", docs, site, use_directory_urls=True, content="# Md")
    original_dest = md.dest_uri
    original_url = md.url
    _run_on_files([md], True, site)
    # The plugin must not rewrite Markdown pages.
    assert md.dest_uri == original_dest
    assert md.url == original_url
    assert md.is_documentation_page() is True  # natively a doc page


# --- 2. Path rewriting: directory URLs --------------------------------------


@pytest.mark.parametrize(
    "src_uri,expected_dest,expected_url",
    [
        ("index.crv", "index.html", "./"),
        ("about.crv", "about/index.html", "about/"),
        ("guide/intro.crv", "guide/intro/index.html", "guide/intro/"),
        ("deep/sub/page.carve", "deep/sub/page/index.html", "deep/sub/page/"),
    ],
)
def test_path_rewrite_directory_urls(dirs, src_uri, expected_dest, expected_url):
    docs, site = dirs
    f = _make_file(src_uri, docs, site, use_directory_urls=True)
    _run_on_files([f], True, site)
    assert f.dest_uri == expected_dest
    # MkDocs renders the homepage index URL as "./" under directory URLs.
    assert f.url == expected_url
    assert os.path.normpath(f.abs_dest_path) == os.path.normpath(
        os.path.join(site, expected_dest)
    )


# --- 3. Path rewriting: flat (use_directory_urls=False) ---------------------


@pytest.mark.parametrize(
    "src_uri,expected_dest",
    [
        ("index.crv", "index.html"),
        ("about.crv", "about.html"),
        ("guide/intro.crv", "guide/intro.html"),
        ("deep/sub/page.carve", "deep/sub/page.html"),
    ],
)
def test_path_rewrite_flat_urls(dirs, src_uri, expected_dest):
    docs, site = dirs
    f = _make_file(src_uri, docs, site, use_directory_urls=False)
    _run_on_files([f], False, site)
    assert f.dest_uri == expected_dest
    assert f.url == expected_dest


# --- 4. README.crv maps to index, like Markdown README.md -------------------


def test_readme_maps_to_index(dirs):
    docs, site = dirs
    f = _make_file("README.crv", docs, site, use_directory_urls=True)
    _run_on_files([f], True, site)
    assert f.dest_uri == "index.html"


# --- 5. Conversion produces expected HTML -----------------------------------


def test_convert_carve_core_output():
    html = convert_carve("# Title\n\nSome *bold* text.\n\n- a\n- b\n")
    assert "<h1>Title" in html
    assert "<strong>bold</strong>" in html
    assert "<li>a</li>" in html


def test_convert_carve_table():
    html = convert_carve("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in html
    assert "<th>a</th>" in html


# --- 6. Extension passthrough changes output --------------------------------


def test_extension_passthrough_changes_output():
    src = "# Hello World\n\ntext\n"
    plain = convert_carve(src, extensions=None)
    with_perma = convert_carve(src, extensions=["heading_permalinks"])
    assert 'class="permalink"' not in plain
    assert 'class="permalink"' in with_perma


def test_plugin_default_extensions_applied(dirs):
    docs, site = dirs
    f = _make_file(
        "index.crv", docs, site, use_directory_urls=True, content="# Hi There\n\ntext"
    )
    plugin = CarvePlugin()
    _run_on_files([f], True, site, plugin=plugin)
    page = SimpleNamespace(file=f)
    out = plugin.on_page_markdown("# Hi There\n\ntext", page=page, config={}, files=None)
    # Default extension list includes heading_permalinks.
    assert 'class="permalink"' in out


def test_plugin_custom_extensions_config(dirs):
    docs, site = dirs
    f = _make_file(
        "m.crv", docs, site, use_directory_urls=True, content="```math\nx^2\n```\n"
    )
    plugin = CarvePlugin()
    plugin.load_config({"extensions": ["math_block"]})
    config = {"use_directory_urls": True, "site_dir": site}
    plugin.on_files(Files([f]), config=config)
    page = SimpleNamespace(file=f)
    out = plugin.on_page_markdown(
        "```math\nx^2\n```\n", page=page, config={}, files=None
    )
    assert 'class="math display"' in out


# --- 7. on_page_markdown leaves .md pages alone -----------------------------


def test_on_page_markdown_passthrough_for_md():
    plugin = CarvePlugin()
    plugin.load_config({})
    page = SimpleNamespace(file=SimpleNamespace(src_uri="page.md"))
    original = "# Markdown stays *raw*"
    assert plugin.on_page_markdown(original, page=page, config={}, files=None) == original


# --- 8. Mixed tree: only carve files rewritten ------------------------------


def test_mixed_tree_only_carve_rewritten(dirs):
    docs, site = dirs
    crv = _make_file("a.crv", docs, site, use_directory_urls=True)
    md = _make_file("b.md", docs, site, use_directory_urls=True, content="# b")
    _run_on_files([crv, md], True, site)
    assert crv.dest_uri == "a/index.html"
    assert crv.is_documentation_page() is True
    # Markdown page keeps native MkDocs handling untouched.
    assert md.dest_uri == "b/index.html"


def test_carve_suffixes_constant():
    assert ".crv" in CARVE_SUFFIXES and ".carve" in CARVE_SUFFIXES
