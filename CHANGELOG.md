# Changelog

Notable changes to the `mkdocs-carve` plugin.

Rendering is done by the Carve engine (`carve-lang`), so an engine change can
alter output with no plugin diff. Engine bumps therefore get an entry of their
own.

## Unreleased

Initial release, not yet published to PyPI.

- Render `.crv` pages as MkDocs documentation pages, alongside Markdown.
- Enable Carve extensions per site through the plugin's `extensions` config key,
  defaulting to `["heading_permalinks"]`.
- Depend on the released `carve-lang>=0.1.0` from PyPI instead of a git
  revision. Installing no longer builds the engine from source, so no Rust
  toolchain is needed - and this package can be published at all, which a
  direct-URL dependency prevented.
