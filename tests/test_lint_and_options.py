"""The `lint` switch and per-extension options in `extensions`."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest
from mkdocs.config.base import ValidationError

from mkdocs_carve.plugin import CarvePlugin, split_extensions

UNATTACHED = "para\n\n{#id .cls}\n"


def _plugin(**options):
    plugin = CarvePlugin()
    errors, warnings = plugin.load_config(options)
    assert not errors and not warnings, (errors, warnings)
    plugin.on_config({"docs_dir": tempfile.mkdtemp(prefix="carve-lint-")})
    return plugin


def _render(plugin, source, src_uri="page.crv"):
    page = SimpleNamespace(file=SimpleNamespace(src_uri=src_uri, abs_src_path=None))
    return plugin.on_page_markdown(source, page=page, config={}, files=None)


# --- lint ------------------------------------------------------------------


def test_lint_is_off_by_default(caplog):
    with caplog.at_level(logging.WARNING):
        _render(_plugin(), UNATTACHED)
    assert not [r for r in caplog.records if "unattached-block-attribute" in r.getMessage()]


def test_a_lint_finding_is_a_warning_located_on_the_page(caplog):
    with caplog.at_level(logging.WARNING):
        _render(_plugin(lint=True), UNATTACHED, "guide/intro.crv")
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "guide/intro.crv:3:1: unattached-block-attribute: " in m for m in messages
    ), messages


def test_a_clean_page_logs_nothing(caplog):
    with caplog.at_level(logging.WARNING):
        _render(_plugin(lint=True), "# Title\n\nClean text.\n")
    assert not caplog.records


def test_lint_never_touches_markdown_pages(caplog):
    with caplog.at_level(logging.WARNING):
        out = _render(_plugin(lint=True), UNATTACHED, "page.md")
    assert out == UNATTACHED
    assert not caplog.records


def test_lint_reads_the_configured_extensions(monkeypatch):
    import carve

    seen = []
    real = carve.lint

    def spy(source, extensions=None):
        seen.append(extensions)
        return real(source, extensions=extensions)

    monkeypatch.setattr(carve, "lint", spy)
    _render(_plugin(lint=True, extensions=["wikilinks"]), "text\n")
    assert seen == [["wikilinks"]]


def _build(tmp_path, lint, strict):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.crv").write_text(UNATTACHED, encoding="utf-8")
    cfg = tmp_path / "mkdocs.yml"
    cfg.write_text(
        "site_name: t\nplugins:\n  - carve:\n      lint: %s\n" % ("true" if lint else "false"),
        encoding="utf-8",
    )
    args = [sys.executable, "-m", "mkdocs", "build", "-f", str(cfg), "--site-dir", str(tmp_path / "site")]
    if strict:
        args.append("--strict")
    return subprocess.run(args, capture_output=True, text=True, cwd=tmp_path)


def test_strict_build_fails_on_a_lint_finding(tmp_path):
    result = _build(tmp_path, lint=True, strict=True)
    assert result.returncode != 0
    assert "unattached-block-attribute" in result.stderr


def test_non_strict_build_warns_and_succeeds(tmp_path):
    result = _build(tmp_path, lint=True, strict=False)
    assert result.returncode == 0, result.stderr
    assert "unattached-block-attribute" in result.stderr


def test_strict_build_without_lint_is_unaffected(tmp_path):
    result = _build(tmp_path, lint=False, strict=True)
    assert result.returncode == 0, result.stderr


# --- extension options -----------------------------------------------------


def test_split_keeps_plain_names_and_collects_options():
    names, options = split_extensions(
        ["math_block", {"wikilinks": {"css_class": "wl"}}, {"list_table": None}]
    )
    assert names == ["math_block", "wikilinks", "list_table"]
    assert options == {"wikilinks": {"css_class": "wl"}}


def test_split_without_options_passes_none():
    assert split_extensions(["a", "b"]) == (["a", "b"], None)


@pytest.mark.parametrize(
    "entry",
    [{"a": {}, "b": {}}, {"wikilinks": "wl"}, {"wikilinks": ["css_class"]}],
)
def test_a_malformed_entry_is_a_configuration_error(entry):
    with pytest.raises(ValidationError):
        split_extensions([entry])


def test_wikilink_options_reach_the_engine():
    plugin = _plugin(
        extensions=[{"wikilinks": {"css_class": "wl", "new_window": True}}]
    )
    out = _render(plugin, "[[Foo Bar]]\n")
    assert 'class="wl"' in out
    assert 'target="_blank"' in out


def test_options_on_the_default_extension_change_its_output():
    plugin = _plugin(extensions=[{"heading_permalinks": {"symbol": "#"}}])
    out = _render(plugin, "# Hi\n")
    assert ">#</a>" in out
    assert "¶" not in out


def test_an_unknown_option_is_refused_before_any_page():
    plugin = CarvePlugin()
    plugin.load_config({"extensions": [{"wikilinks": {"url_template": "/w/{}"}}]})
    with pytest.raises(ValidationError, match="url_template"):
        plugin.on_config({"docs_dir": os.getcwd()})


def test_an_unknown_extension_name_is_refused_before_any_page():
    plugin = CarvePlugin()
    plugin.load_config({"extensions": ["no_such_extension"]})
    with pytest.raises(ValidationError, match="no_such_extension"):
        plugin.on_config({"docs_dir": os.getcwd()})


def test_options_reach_the_engine_on_the_include_path(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "frag.crv").write_text("[[Foo Bar]]\n", encoding="utf-8")
    page_path = docs / "page.crv"
    page_path.write_text("{{ frag.crv }}\n", encoding="utf-8")
    plugin = CarvePlugin()
    plugin.load_config(
        {"includes": True, "extensions": [{"wikilinks": {"css_class": "wl"}}]}
    )
    plugin.on_config({"docs_dir": str(docs)})
    page = SimpleNamespace(
        file=SimpleNamespace(src_uri="page.crv", abs_src_path=str(page_path))
    )
    out = plugin.on_page_markdown(
        page_path.read_text(encoding="utf-8"), page=page, config={}, files=None
    )
    assert 'class="wl"' in out


def test_an_option_of_the_wrong_type_names_the_option_not_the_engine():
    plugin = CarvePlugin()
    plugin.load_config({"extensions": [{"wikilinks": {"new_window": "false"}}]})
    with pytest.raises(ValidationError) as caught:
        plugin.on_config({"docs_dir": os.getcwd()})
    assert "new_window" in str(caught.value)
    assert "upgrade" not in str(caught.value)


# --- lint across includes --------------------------------------------------


def _include_site(tmp_path, includes=True):
    docs = tmp_path / "docs"
    (docs / "parts").mkdir(parents=True)
    (docs / "parts" / "frag.crv").write_text(UNATTACHED, encoding="utf-8")
    page_path = docs / "page.crv"
    page_path.write_text("Intro.\n\n{{ parts/frag.crv }}\n\n{{ missing.crv }}\n", encoding="utf-8")
    plugin = CarvePlugin()
    plugin.load_config({"lint": True, "includes": includes})
    plugin.on_config({"docs_dir": str(docs)})
    page = SimpleNamespace(file=SimpleNamespace(src_uri="page.crv", abs_src_path=str(page_path)))
    return plugin, page, page_path.read_text(encoding="utf-8")


def test_a_finding_inside_an_included_file_names_the_file_and_the_site(tmp_path, caplog):
    plugin, page, source = _include_site(tmp_path)
    with caplog.at_level(logging.WARNING):
        plugin.on_page_markdown(source, page=page, config={}, files=None)
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "page.crv: parts/frag.crv:3:1: unattached-block-attribute: " in m
        and m.endswith("(included at page.crv:3:1)")
        for m in messages
    ), messages


def test_an_unresolved_include_is_warned_once_not_twice(tmp_path, caplog):
    plugin, page, source = _include_site(tmp_path)
    with caplog.at_level(logging.WARNING):
        plugin.on_page_markdown(source, page=page, config={}, files=None)
    unresolved = [r for r in caplog.records if "include-unresolved" in r.getMessage()]
    assert len(unresolved) == 1, [r.getMessage() for r in unresolved]


def test_included_files_are_not_linted_while_includes_are_off(tmp_path, caplog):
    plugin, page, source = _include_site(tmp_path, includes=False)
    with caplog.at_level(logging.WARNING):
        plugin.on_page_markdown(source, page=page, config={}, files=None)
    assert not [r for r in caplog.records if "frag.crv" in r.getMessage()]
