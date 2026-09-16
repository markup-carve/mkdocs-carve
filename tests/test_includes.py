"""Include expansion: containment, denials, and what a reader is shown.

These need an engine that exposes ``carve.render_with_includes``. The pinned
engine in ``constraints-ci.txt`` predates it, so the ``includes`` CI job
installs one that has it; the skip below is what keeps the pinned job honest
about not having measured this.
"""

from __future__ import annotations

import logging
import os
import tempfile
from types import SimpleNamespace

import carve
import pytest
from mkdocs.config.base import ValidationError
from mkdocs.structure.files import File

from mkdocs_carve.plugin import CarvePlugin

pytestmark = pytest.mark.skipif(
    not hasattr(carve, "render_with_includes"),
    reason="installed carve-lang exposes no render_with_includes",
)


@pytest.fixture()
def site():
    """A docs tree with a fragment inside the root and a file outside it."""
    base = tempfile.mkdtemp(prefix="carve-inc-")
    docs = os.path.join(base, "docs")
    os.makedirs(os.path.join(docs, "sub"))
    os.makedirs(os.path.join(base, "outside"))
    _write(os.path.join(docs, "sub", "frag.crv"), "fragment with :crv:\n")
    _write(os.path.join(base, "outside", "secret.crv"), "UNCONTAINED BODY\n")
    return SimpleNamespace(base=base, docs=docs, site_dir=os.path.join(base, "site"))


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _plugin(site, **options):
    plugin = CarvePlugin()
    errors, warnings = plugin.load_config(options)
    assert not errors and not warnings, (errors, warnings)
    plugin.on_config({"docs_dir": site.docs})
    return plugin


def _page(site, src_uri, source):
    _write(os.path.join(site.docs, src_uri), source)
    file = File(src_uri, site.docs, site.site_dir, use_directory_urls=True)
    return SimpleNamespace(file=file)


def _render(plugin, site, src_uri, source):
    page = _page(site, src_uri, source)
    return plugin.on_page_markdown(source, page=page, config={}, files=None)


# --- the switch ------------------------------------------------------------


def test_directive_stays_literal_while_includes_are_off(site):
    plugin = _plugin(site)
    html = _render(plugin, site, "index.crv", "{{ sub/frag.crv }}\n")
    assert "{{ sub/frag.crv }}" in html
    assert "fragment" not in html


def test_enabling_includes_expands_the_directive(site):
    plugin = _plugin(site, includes=True)
    html = _render(plugin, site, "index.crv", "{{ sub/frag.crv }}\n")
    assert "fragment" in html
    assert "{{ sub/frag.crv }}" not in html


# --- the root --------------------------------------------------------------


def test_default_root_is_the_docs_directory(site):
    plugin = _plugin(site, includes=True)
    assert plugin._include_root == os.path.abspath(site.docs)


def test_configured_relative_root_is_refused_rather_than_resolved(site):
    """The engine's refusal is the containment guarantee; it has to fire here."""
    with pytest.raises(ValidationError) as caught:
        _plugin(site, includes=True, include_root="docs")
    assert "absolute" in str(caught.value)


def test_configured_root_reaches_the_engine_unchanged(site):
    """A root above docs_dir widens containment, which is what it is for."""
    plugin = _plugin(site, includes=True, include_root=site.base)
    html = _render(plugin, site, "index.crv", "{{ ../outside/secret.crv }}\n")
    assert "UNCONTAINED BODY" in html


# --- denials ---------------------------------------------------------------


def test_traversal_out_of_the_root_is_not_expanded(site):
    plugin = _plugin(site, includes=True)
    html = _render(plugin, site, "index.crv", "{{ ../outside/secret.crv }}\n")
    assert "UNCONTAINED BODY" not in html


def test_denial_classes_reach_the_build_log(site, caplog):
    plugin = _plugin(site, includes=True)
    source = "{{ ../outside/secret.crv }}\n\n{{ nope.crv }}\n"
    with caplog.at_level(logging.INFO):
        _render(plugin, site, "index.crv", source)
    logged = [record.getMessage() for record in caplog.records]
    assert any("outside-root" in message for message in logged)
    assert any("not-found" in message for message in logged)


def test_the_page_warning_does_not_say_which_denial_it_was(site, caplog):
    """Spec I7: one warning for both, so a page cannot probe the filesystem."""
    plugin = _plugin(site, includes=True)
    with caplog.at_level(logging.WARNING):
        _render(plugin, site, "index.crv", "{{ ../outside/secret.crv }}\n")
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    ]
    assert warnings, "a refused include reported nothing"
    assert all("include-unresolved" in message for message in warnings)
    assert not any("outside-root" in message for message in warnings)


def test_a_warning_is_located_on_the_page_that_asked(site, caplog):
    plugin = _plugin(site, includes=True)
    with caplog.at_level(logging.WARNING):
        _render(plugin, site, "guide.crv", "{{ nope.crv }}\n")
    assert any("guide.crv" in r.getMessage() for r in caplog.records)


def test_no_host_path_reaches_a_reported_message(site, caplog):
    """A page outside the root is where an absolute identity would leak one.

    Inside the root the engine relativizes whatever it is given, so a contained
    page cannot tell an absolute identity from a relative one. With the root
    narrowed below the page, it can.
    """
    plugin = _plugin(site, includes=True, include_root=os.path.join(site.docs, "sub"))
    with caplog.at_level(logging.INFO):
        _render(plugin, site, "index.crv", "{{ nope.crv }}\n")
    assert caplog.records, "a refused include reported nothing"
    for record in caplog.records:
        assert site.base not in record.getMessage()


# --- what the engine is asked to do ---------------------------------------


def test_a_path_resolves_against_the_page_that_wrote_it(site):
    """The page's own identity, not the root, is what a sibling resolves against.

    An earlier version of this asserted on a nested include and passed with the
    page identity hardcoded, because the nesting resolved against the child
    either way. Only a page below the root can tell the two apart.
    """
    plugin = _plugin(site, includes=True)
    html = _render(plugin, site, "sub/page.crv", "{{ frag.crv }}\n")
    assert "fragment" in html


def test_nested_relative_paths_resolve_against_the_including_file(site):
    os.makedirs(os.path.join(site.docs, "sub", "deep"))
    _write(os.path.join(site.docs, "sub", "deep", "inner.crv"), "inner text\n")
    _write(os.path.join(site.docs, "sub", "frag.crv"), "{{ deep/inner.crv }}\n")
    plugin = _plugin(site, includes=True)
    html = _render(plugin, site, "index.crv", "{{ sub/frag.crv }}\n")
    assert "inner text" in html


def test_a_cycle_degrades_instead_of_hanging(site, caplog):
    _write(os.path.join(site.docs, "a.crv"), "A {{ b.crv }}\n")
    _write(os.path.join(site.docs, "b.crv"), "B {{ a.crv }}\n")
    plugin = _plugin(site, includes=True)
    with caplog.at_level(logging.WARNING):
        html = _render(plugin, site, "index.crv", "{{ a.crv }}\n")
    assert "A B" in html
    assert any("include-cycle" in r.getMessage() for r in caplog.records)


def test_the_symbol_map_reaches_an_included_child(site):
    plugin = _plugin(site, includes=True, symbols={"crv": "CARVE"})
    html = _render(plugin, site, "index.crv", "{{ sub/frag.crv }}\n")
    assert "CARVE" in html
    assert ":crv:" not in html


def test_the_extension_set_reaches_an_included_child(site):
    _write(os.path.join(site.docs, "sub", "frag.crv"), "# Child\n")
    plugin = _plugin(site, includes=True, extensions=["heading_permalinks"])
    html = _render(plugin, site, "index.crv", "{{ sub/frag.crv }}\n")
    assert "permalink" in html


# --- rebuilds --------------------------------------------------------------


def test_serve_watches_the_containment_root(site):
    plugin = _plugin(site, includes=True)
    watched = []
    server = SimpleNamespace(watch=watched.append)
    plugin.on_serve(server, config={}, builder=None)
    assert watched == [os.path.abspath(site.docs)]


def test_serve_watches_nothing_while_includes_are_off(site):
    plugin = _plugin(site)
    watched = []
    server = SimpleNamespace(watch=watched.append)
    plugin.on_serve(server, config={}, builder=None)
    assert watched == []
