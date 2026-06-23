# mkdocs-carve

A [MkDocs](https://www.mkdocs.org/) plugin that renders
[Carve](https://github.com/markup-carve) (`.crv` / `.carve`) source files as
documentation pages, converting them to HTML with the
[python-carve](https://github.com/markup-carve/python-carve) engine. Carve pages
are wrapped by your active MkDocs theme exactly like Markdown pages, and they
coexist with `.md` pages in the same `docs/` tree.

## Installation

```bash
pip install mkdocs-carve
```

> [!IMPORTANT]
> The Carve engine (`carve`, from python-carve) is a native extension built with
> Rust via [maturin](https://www.maturin.rs/). Until python-carve is published to
> PyPI, installing this plugin pulls `carve` from git and **builds a native wheel
> at install time, so a Rust toolchain (`cargo`) must be available**. Install Rust
> from <https://rustup.rs> if you do not have it. Once python-carve ships a
> prebuilt wheel on PyPI, no toolchain will be needed.

The dependency is declared as:

```
carve @ git+https://github.com/markup-carve/python-carve
```

## Usage

Enable the plugin in `mkdocs.yml`:

```yaml
site_name: My Site
plugins:
  - carve
```

Then write pages with a `.crv` (or `.carve`) extension under `docs/` and
reference them in `nav` by their source path:

```yaml
nav:
  - Home: index.crv
  - About: about.crv
  - Guide:
      - Introduction: guide/intro.crv
  - Changelog: changelog.md   # plain Markdown still works
```

A Carve page, `docs/index.crv`:

```
# Carve in MkDocs

This homepage is written in *Carve* (note: `*bold*` is strong,
`/italic/` is emphasis in Carve).

- lists
- `inline code`
- [links](https://example.com)

| feature | works |
|---------|-------|
| tables  | yes   |
```

## Configuration

| Option       | Type         | Default                  | Description |
|--------------|--------------|--------------------------|-------------|
| `extensions` | list of str  | `["heading_permalinks"]` | Carve extension names enabled for every Carve page. Passed straight to `carve.to_html`. Set to `[]` to use the core renderer only. |

Example enabling additional Carve extensions:

```yaml
plugins:
  - carve:
      extensions:
        - heading_permalinks
        - math_block
        - list_table
```

Available extension names come from the carve engine
(`python -c "import carve; print(carve.extensions())"`); at the time of writing:
`autolink`, `details`, `external_links`, `fenced_render`, `heading_permalinks`,
`list_table`, `math_block`, `spoiler`, `tab_normalize`, `wikilinks`, `citations`.

## How it works

* **`on_files`** promotes each `.crv` / `.carve` file to a documentation page
  and recomputes its destination path and URL using the *same* rules MkDocs
  applies to Markdown (driven by the file stem and `use_directory_urls`). This
  handles `index` pages, `README` files, nested folders, and both
  `use_directory_urls: true` and `false` modes without hand-rolled path logic.
* The Carve file keeps its original `.crv` / `.carve` `src_uri`, so `nav`
  entries that reference `.crv` paths resolve without translation.
* **`on_page_markdown`** converts the Carve source to an HTML fragment. MkDocs'
  Markdown step passes raw HTML through untouched, so the theme template wraps
  the converted output like any normal page.

## Development

```bash
pip install -e .[test]
pytest
```

The bundled `example/` directory is a complete MkDocs site (Carve homepage,
nested Carve page, a Markdown page, and nav entries) used by the end-to-end
build test. Build it directly with:

```bash
cd example
mkdocs build --strict
```

## License

MIT. See [LICENSE](LICENSE).
