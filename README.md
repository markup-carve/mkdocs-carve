# mkdocs-carve

A [MkDocs](https://www.mkdocs.org/) plugin that renders
[Carve](https://github.com/markup-carve) (`.crv`) source files as
documentation pages, converting them to HTML with the
[carve-py](https://github.com/markup-carve/carve-py) engine. Carve pages
are wrapped by your active MkDocs theme exactly like Markdown pages, and they
coexist with `.md` pages in the same `docs/` tree.

## Installation

```bash
pip install mkdocs-carve
```

The Carve engine (`carve-lang`, the PyO3 binding over carve-rs) is installed
from PyPI as a normal dependency. It ships prebuilt abi3 wheels for Linux, macOS
and Windows, so no Rust toolchain is needed.

## Usage

Enable the plugin in `mkdocs.yml`:

```yaml
site_name: My Site
plugins:
  - carve
```

Then write pages with a `.crv` extension under `docs/` and
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

Available extension names come from the installed Carve engine, so ask it rather
than trusting a list in a README that cannot know which engine build you have:

```bash
python -c "import carve; print(carve.extensions())"
```

## How it works

* **`on_files`** promotes each `.crv` file to a documentation page
  and recomputes its destination path and URL using the *same* rules MkDocs
  applies to Markdown (driven by the file stem and `use_directory_urls`). This
  handles `index` pages, `README` files, nested folders, and both
  `use_directory_urls: true` and `false` modes without hand-rolled path logic.
* The Carve file keeps its original `.crv` `src_uri`, so `nav`
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
