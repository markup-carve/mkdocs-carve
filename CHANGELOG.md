# Changelog

Notable changes to the `mkdocs-carve` plugin.

Rendering is done by the Carve engine (`carve-lang`), so an engine change can
alter output with no plugin diff. Engine bumps therefore get an entry of their
own.

## Unreleased

- The engine CI measures moves from `carve-lang` 0.1.4 to 0.1.7, so a run here
  measures what PyPI serves rather than an engine three releases behind it. Four
  renderings change with it, each visible on a built page: a cross-reference
  whose target differs only in case stays literal text rather than resolving; a
  named container whose metadata slot is not separated by a space opens the
  container rather than rendering its opener as prose; explicit table body
  counts are consumed into one `<tbody>` per count instead of leaking into the
  page as a `body-rows` attribute on `<table>`; and a fence that is a
  description body's own block gives an empty payload no content.
  markup-carve/mkdocs-carve#26
- `tests/test_rendering_rulings.py` holds the engine to those four by direction
  rather than by a golden. Nothing in the suite could see a rendering change
  before, so the daily unconstrained run in `scheduled.yml` stayed green through
  three engine releases while all four shapes rendered differently.
  markup-carve/mkdocs-carve#26

The declared floor stays at `carve-lang>=0.1.1`. It is a claim about the oldest
engine the plugin works with, and 0.1.4 still passes every other test; moving it
is a separate decision from the pin above.

## 0.1.1 - 2026-09-21

- Expand `{{ path }}` includes for file-backed pages, contained to a root, via
  new `includes` and `include_root` config keys. Off by default; a directive
  stays literal until a site asks. Needs `carve-lang` 0.1.4 or newer, above the
  declared floor: `includes: true` on an older engine is a configuration error
  rather than a silent no-op. markup-carve/mkdocs-carve#17

## 0.1.0 - 2026-08-27

- Render `.crv` pages as MkDocs documentation pages, alongside Markdown.
- Enable Carve extensions per site through the plugin's `extensions` config key,
  defaulting to `["heading_permalinks"]`.
- Depend on the released `carve-lang` from PyPI instead of a git revision.
  Installing no longer builds the engine from source, so no Rust toolchain is
  needed - and this package can be published at all, which a direct-URL
  dependency prevented.
- Forward a symbol map to the engine, so `:smile:` need not render as literal
  text. New `emoji` (`none`/`unicode`/`twemoji`, read from the emoji database
  the site's Markdown pages already use) and `symbols` (an inline mapping, or a
  path to a JSON file) config keys. Mapped values are emitted RAW, so the map is
  read only from `mkdocs.yml` and a JSON path named there - never from page
  content. markup-carve/mkdocs-carve#8
- Report when the engine floor can be raised: a probe that stays quiet while the
  newest published engine is vulnerable and fails the day a patched one appears.
- Raise the engine floor to `carve-lang>=0.1.1`. 0.1.0 renders
  `srcset="safe.png 1x, javascript:alert(1) 2x"` unsanitized (Carve 0.1.3's
  list-valued URL attribute defect); 0.1.1 carries the fix, which is what the
  probe above reported.
- Bound the engine dependency at `carve-lang>=0.1.1,<0.2.0`. Release gates are
  pinned to current `carve-lang` 0.1.2, while 0.1.1 remains a valid supported
  floor. On the engine's own
  0.x scheme `0.1` is the major, so the previous open range admitted breaking
  releases by the engine's own rules. markup-carve/mkdocs-carve#10
