# Changelog

Notable changes to the `mkdocs-carve` plugin.

Rendering is done by the Carve engine (`carve-lang`), so an engine change can
alter output with no plugin diff. Engine bumps therefore get an entry of their
own.

## Unreleased

Initial release, not yet published to PyPI. It cannot be published until
`carve-lang` is on PyPI - see `RELEASING.md`.

- Render `.crv` pages as MkDocs documentation pages, alongside Markdown.
- Enable Carve extensions per site through the plugin's `extensions` config key,
  defaulting to `["heading_permalinks"]`.
- Pin the Carve engine to an exact revision, so two installs a day apart cannot
  differ silently.
