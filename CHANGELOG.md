# Changelog

Notable changes to the `mkdocs-carve` plugin.

Rendering is done by the Carve engine (`carve-lang`), so an engine change can
alter output with no plugin diff. Engine bumps therefore get an entry of their
own.

## Unreleased

Prepared as 0.1.0. Not released: see the note below.

- Render `.crv` pages as MkDocs documentation pages, alongside Markdown.
- Enable Carve extensions per site through the plugin's `extensions` config key,
  defaulting to `["heading_permalinks"]`.
- Depend on the released `carve-lang>=0.1.0` from PyPI instead of a git
  revision. Installing no longer builds the engine from source, so no Rust
  toolchain is needed - and this package can be published at all, which a
  direct-URL dependency prevented.
- Report when the engine floor can be raised. `carve-lang>=0.1.0` is an open
  floor, so what installs is whatever PyPI serves as latest, and no other test
  here can tell a patched engine from a vulnerable one. A strict `xfail` probe
  stays quiet while the newest published engine is vulnerable and FAILS the day
  a patched one appears, which is the day the floor should move.

### Not released, and why

`carve-lang` on PyPI is 0.1.0, published 2026-08-12, which predates the Carve
0.1.3 security release: a list-valued URL attribute was probed only on its FIRST
entry, so `srcset="safe.png 1x, javascript:alert(1) 2x"` passed sanitization on
the second one. Verified by installing that exact release and rendering the
case, which comes back unsanitized.

The suite is green against it - 25 of 25 before the probe above was added -
because nothing else here can see the difference. Publishing today would ship a
plugin whose every consumer resolves a vulnerable engine, and the floor cannot
be raised because no patched `carve-lang` exists on PyPI to raise it to.

This release waits on python-carve publishing. Its `main` already carries the
fix and reports 0.1.1, so the floor becomes `carve-lang>=0.1.1` at that point.
