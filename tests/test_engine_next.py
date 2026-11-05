"""Readings of the carve-lang release after 0.1.12, as a site build sees them.

Directions, not goldens, like ``test_rendering_rulings``. These need the next
engine; ``constraints-ci.txt`` is what guarantees it.
"""

from __future__ import annotations

import logging
import os
import tempfile
from types import SimpleNamespace

from mkdocs.structure.files import File

from mkdocs_carve.plugin import CarvePlugin, convert_carve


def _plugin(docs_dir, **options):
    plugin = CarvePlugin()
    errors, warnings = plugin.load_config(options)
    assert not errors and not warnings, (errors, warnings)
    plugin.on_config({"docs_dir": docs_dir})
    return plugin


def _render(plugin, docs_dir, src_uri, source):
    with open(os.path.join(docs_dir, src_uri), "w", encoding="utf-8") as handle:
        handle.write(source)
    file = File(src_uri, docs_dir, os.path.join(docs_dir, "_site"), use_directory_urls=True)
    page = SimpleNamespace(file=file)
    return plugin.on_page_markdown(source, page=page, config={}, files=None)


def _lint_messages(caplog, source):
    docs = tempfile.mkdtemp(prefix="carve-next-")
    with caplog.at_level(logging.WARNING):
        _render(_plugin(docs, lint=True), docs, "page.crv", source)
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


# --- table alignment (markup-carve/carve#5091 D3) ---------------------------


def test_braced_alignment_aligns_the_column():
    html = convert_carve("|={>} Price |= Name |\n| 1 | a |\n")
    assert "<thead>" in html
    assert '<th scope="col" style="text-align: right;">Price</th>' in html
    assert '<td style="text-align: right;">1</td>' in html


def test_glued_alignment_still_renders_but_lint_reports_it(caplog):
    source = "|=> Price |= Name |\n| 1 | a |\n"
    assert 'style="text-align: right;"' in convert_carve(source)
    messages = _lint_messages(caplog, source)
    assert any("page.crv:1:" in m and "deprecated-cell-alignment" in m for m in messages), messages


def test_braced_alignment_is_lint_clean(caplog):
    assert not _lint_messages(caplog, "|={>} Price |= Name |\n| 1 | a |\n")


# --- thematic breaks (markup-carve/carve#4973) ------------------------------


def test_a_dash_thematic_break_is_a_lint_finding(caplog):
    messages = _lint_messages(caplog, "a\n\n---\n\nb\n")
    assert any("page.crv:3:1: thematic-break-spelling" in m for m in messages), messages


def test_the_canonical_thematic_break_is_lint_clean(caplog):
    assert not _lint_messages(caplog, "a\n\n***\n\nb\n")


# --- CSV and TSV table includes ---------------------------------------------


def test_table_include_selects_rows_and_columns(caplog):
    docs = tempfile.mkdtemp(prefix="carve-next-")
    with open(os.path.join(docs, "plans.csv"), "w", encoding="utf-8") as handle:
        handle.write("Plan,Seats,Price\nFree,1,0\nTeam,10,20\nCorp,100,90\n")
    source = '{table}\n{{ plans.csv @code:csv @rows:3-4 @cols:"Price,Plan" }}\n'
    with caplog.at_level(logging.WARNING):
        html = _render(_plugin(docs, includes=True), docs, "index.crv", source)
    assert not caplog.records, [r.getMessage() for r in caplog.records]
    assert '<th scope="col">Price</th><th scope="col">Plan</th>' in html
    assert "<td>20</td><td>Team</td>" in html
    assert "<td>90</td><td>Corp</td>" in html
    assert "Free" not in html
    assert "Seats" not in html
