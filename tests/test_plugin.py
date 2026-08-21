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
from mkdocs.config.base import ValidationError
from mkdocs.structure.files import File, Files

from mkdocs_carve.plugin import (
    CARVE_SUFFIXES,
    DEFAULT_EXTENSIONS,
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
        ("deep/sub/page.crv", "deep/sub/page/index.html", "deep/sub/page/"),
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
        ("deep/sub/page.crv", "deep/sub/page.html"),
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
    # Match the cell content, not the engine's exact attribute list: 0.1.1
    # added `scope="col"` to header cells, and the plugin does not own that
    # markup - pinning it turns an engine improvement into a plugin failure.
    assert ">a</th>" in html


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
    assert ".crv" in CARVE_SUFFIXES and ".carve" not in CARVE_SUFFIXES


# --- 9. Symbol map: config plumbing ----------------------------------------
#
# The engine emits a mapped value RAW, so these tests care about two things:
# that the map arrives at all, and that its only possible source is the site's
# own configuration. `tests/test_symbols.py` covers the map's contents.


def _configured(**settings):
    """A plugin with `settings` applied and `on_config` already run."""
    plugin = CarvePlugin()
    errors, warnings = plugin.load_config(settings)
    assert errors == [] and warnings == [], (errors, warnings)
    plugin.on_config({"config_file_path": settings.pop("_config_file", "mkdocs.yml")})
    return plugin


def _render(plugin, source):
    page = SimpleNamespace(file=SimpleNamespace(src_uri="p.crv"))
    return plugin.on_page_markdown(source, page=page, config={}, files=None)


def test_no_symbol_map_leaves_a_page_exactly_as_before():
    """The default has to stay byte-identical, not merely similar."""
    plugin = _configured()
    assert plugin._symbols is None
    source = "# T\n\nA :smile: and text.\n"
    assert _render(plugin, source) == convert_carve(
        source, extensions=list(DEFAULT_EXTENSIONS)
    )


def test_an_inline_map_reaches_the_engine():
    plugin = _configured(symbols={"smile": "SMILED"})
    assert "SMILED" in _render(plugin, "A :smile: here")


def test_an_unmapped_name_stays_literal():
    plugin = _configured(symbols={"smile": "SMILED"})
    assert ":frown:" in _render(plugin, "A :frown: here")


def test_the_word_boundary_guard_survives_the_plugin():
    plugin = _configured(symbols={"smile": "SMILED"})
    out = _render(plugin, "a:smile:b and 3:smile:4 and `:smile:` but A :smile: here")
    assert out.count("SMILED") == 1
    assert "a:smile:b" in out
    assert "3:smile:4" in out


def test_emoji_mode_populates_the_map_without_any_symbols_key():
    plugin = _configured(emoji="unicode")
    assert "\U0001f604" in _render(plugin, "A :smile: here")


def test_the_sites_own_entry_wins_over_the_emoji_table():
    plugin = _configured(emoji="unicode", symbols={"smile": "MINE"})
    assert "MINE" in _render(plugin, "A :smile: here")


def test_a_mapped_value_is_not_escaped_on_its_way_through_the_plugin():
    plugin = _configured(symbols={"logo": "<img src='/l.svg'>"})
    out = _render(plugin, ":logo: x")
    assert "<img src='/l.svg'>" in out and "&lt;img" not in out


# --- 10. Symbol map: the JSON file form ------------------------------------


def _with_symbol_file(tmp_path, text):
    config_file = tmp_path / "mkdocs.yml"
    config_file.write_text("site_name: t\n", encoding="utf-8")
    (tmp_path / "symbols.json").write_text(text, encoding="utf-8")
    plugin = CarvePlugin()
    plugin.load_config({"symbols": "symbols.json"})
    plugin.on_config({"config_file_path": str(config_file)})
    return plugin


def test_a_json_path_resolves_relative_to_the_config_file(tmp_path):
    plugin = _with_symbol_file(tmp_path, '{"crv": "<abbr>CRV</abbr>"}')
    assert "<abbr>CRV</abbr>" in _render(plugin, "a :crv: file")


def test_a_json_path_in_a_subdirectory_resolves(tmp_path):
    config_file = tmp_path / "mkdocs.yml"
    config_file.write_text("site_name: t\n", encoding="utf-8")
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "s.json").write_text('{"a": "A"}', encoding="utf-8")
    plugin = CarvePlugin()
    plugin.load_config({"symbols": "cfg/s.json"})
    plugin.on_config({"config_file_path": str(config_file)})
    assert "A" in _render(plugin, "an :a: here")


def test_a_missing_symbol_file_names_the_file(tmp_path):
    config_file = tmp_path / "mkdocs.yml"
    config_file.write_text("site_name: t\n", encoding="utf-8")
    plugin = CarvePlugin()
    plugin.load_config({"symbols": "gone.json"})
    with pytest.raises(ValidationError, match="gone.json"):
        plugin.on_config({"config_file_path": str(config_file)})


def test_malformed_json_is_a_named_error_not_a_traceback(tmp_path):
    with pytest.raises(ValidationError, match="symbols.json"):
        _with_symbol_file(tmp_path, "{not json")


def test_a_json_map_whose_values_are_not_strings_is_refused(tmp_path):
    with pytest.raises(ValidationError, match="must map a name to a string"):
        _with_symbol_file(tmp_path, '{"a": 3}')


# --- 11. Settings the config scheme itself refuses --------------------------


@pytest.mark.parametrize("value", [5, ["a"], True])
def test_symbols_must_be_a_mapping_or_a_path(value):
    errors, _ = CarvePlugin().load_config({"symbols": value})
    assert [key for key, _ in errors] == ["symbols"]


def test_emoji_must_be_one_of_the_three_modes():
    errors, _ = CarvePlugin().load_config({"emoji": "emojione"})
    assert [key for key, _ in errors] == ["emoji"]


def test_an_inline_map_with_a_non_string_value_is_refused():
    plugin = CarvePlugin()
    plugin.load_config({"symbols": {"a": 3}})
    with pytest.raises(ValidationError, match="must map a name to a string"):
        plugin.on_config({"config_file_path": "mkdocs.yml"})


# --- 12. The emoji index follows the site's Markdown configuration ----------


def _tiny_index(_options, _md):
    return {"name": "tiny", "emoji": {":only:": {"unicode": "1f600"}}, "aliases": {}}


def test_the_sites_own_emoji_index_is_used_when_it_configures_one():
    """Material points `pymdownx.emoji` at an extended table; follow it."""
    plugin = CarvePlugin()
    plugin.load_config({"emoji": "unicode"})
    plugin.on_config(
        {
            "config_file_path": "mkdocs.yml",
            "mdx_configs": {"pymdownx.emoji": {"emoji_index": _tiny_index}},
        }
    )
    assert plugin._symbols == {"only": "\U0001f600"}


def test_a_non_callable_emoji_index_falls_back_rather_than_failing():
    """The setting belongs to another extension; do not fail its build."""
    plugin = CarvePlugin()
    plugin.load_config({"emoji": "unicode"})
    plugin.on_config(
        {
            "config_file_path": "mkdocs.yml",
            "mdx_configs": {"pymdownx.emoji": {"emoji_index": "not-callable"}},
        }
    )
    assert "\U0001f604" in plugin._symbols["smile"]
