# Changelog

Notable changes to the `mkdocs-carve` plugin.

Rendering is done by the Carve engine (`carve-lang`), so an engine change can
alter output with no plugin diff. Engine bumps therefore get an entry of their
own.

## Unreleased

Prepared as 0.1.0. Releasing is the maintainer's call.

- Render `.crv` pages as MkDocs documentation pages, alongside Markdown.
- Enable Carve extensions per site through the plugin's `extensions` config key,
  defaulting to `["heading_permalinks"]`.
- Depend on the released `carve-lang` from PyPI instead of a git revision.
  Installing no longer builds the engine from source, so no Rust toolchain is
  needed - and this package can be published at all, which a direct-URL
  dependency prevented.
- Report when the engine floor can be raised: a probe that stays quiet while the
  newest published engine is vulnerable and fails the day a patched one appears.
- Raise the engine floor to `carve-lang>=0.1.1`. 0.1.0 renders
  `srcset="safe.png 1x, javascript:alert(1) 2x"` unsanitized (Carve 0.1.3's
  list-valued URL attribute defect); 0.1.1 carries the fix, which is what the
  probe above reported.
