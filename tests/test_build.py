"""End-to-end test: run a real `mkdocs build` on the example site.

Builds the bundled ``example/`` site in both ``use_directory_urls`` modes and
asserts the generated HTML contains the converted Carve output wrapped in the
theme, that the Markdown page still builds, and that nav links resolve.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(__file__)
EXAMPLE = os.path.normpath(os.path.join(HERE, "..", "example"))


def _build(use_directory_urls):
    """Build the example site into a temp dir; return the site path."""
    site_dir = tempfile.mkdtemp(prefix="carve-build-")
    cfg = os.path.join(EXAMPLE, "mkdocs.yml")
    extra = []
    if not use_directory_urls:
        # Append an override config file so the source example stays clean.
        tmp_cfg = os.path.join(EXAMPLE, "_test_flat.yml")
        with open(cfg, encoding="utf-8") as src, open(tmp_cfg, "w", encoding="utf-8") as dst:
            dst.write(src.read())
            dst.write("\nuse_directory_urls: false\n")
        cfg = tmp_cfg
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mkdocs",
                "build",
                "--strict",
                "-f",
                cfg,
                "--site-dir",
                site_dir,
            ],
            capture_output=True,
            text=True,
        )
    finally:
        if not use_directory_urls and os.path.exists(cfg):
            os.remove(cfg)
    assert result.returncode == 0, f"mkdocs build failed:\n{result.stderr}"
    return site_dir


def _read(site_dir, rel):
    with open(os.path.join(site_dir, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def site_dir_dirurls():
    d = _build(use_directory_urls=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="module")
def site_dir_flat():
    d = _build(use_directory_urls=False)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_directory_urls_pages_exist(site_dir_dirurls):
    for rel in ["index.html", "about/index.html", "guide/intro/index.html", "markdown-page/index.html"]:
        assert os.path.exists(os.path.join(site_dir_dirurls, rel)), rel


def test_directory_urls_homepage_content_and_theme(site_dir_dirurls):
    html = _read(site_dir_dirurls, "index.html")
    assert "<html" in html  # wrapped by the theme
    assert "Carve in MkDocs" in html
    assert "<strong>mkdocs-carve</strong>" in html
    assert "<table>" in html
    assert "<li>Carve supports lists</li>" in html
    assert 'class="permalink"' in html  # default extension active


def test_directory_urls_nested_and_md(site_dir_dirurls):
    guide = _read(site_dir_dirurls, "guide/intro/index.html")
    assert "Guide Introduction" in guide
    assert "<table>" in guide
    md = _read(site_dir_dirurls, "markdown-page/index.html")
    assert "Plain Markdown Page" in md
    assert "<strong>Markdown</strong>" in md


def test_directory_urls_nav_links_resolve(site_dir_dirurls):
    html = _read(site_dir_dirurls, "index.html")
    assert 'href="about/"' in html
    assert 'href="guide/intro/"' in html
    assert 'href="markdown-page/"' in html


def test_flat_pages_exist(site_dir_flat):
    for rel in ["index.html", "about.html", "guide/intro.html", "markdown-page.html"]:
        assert os.path.exists(os.path.join(site_dir_flat, rel)), rel


def test_flat_content_and_nav(site_dir_flat):
    html = _read(site_dir_flat, "index.html")
    assert "Carve in MkDocs" in html
    assert 'href="about.html"' in html
    assert 'href="guide/intro.html"' in html
    about = _read(site_dir_flat, "about.html")
    assert "About" in about
