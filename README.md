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

| Option       | Type                | Default                  | Description |
|--------------|---------------------|--------------------------|-------------|
| `extensions` | list of str         | `["heading_permalinks"]` | Carve extension names enabled for every Carve page. Passed straight to `carve.to_html`. Set to `[]` to use the core renderer only. |
| `emoji`      | `none` \| `unicode` \| `twemoji` | `none` | Resolve `:smile:` and friends through the emoji database your Markdown pages already use. See [Symbols and emoji](#symbols-and-emoji). |
| `symbols`    | mapping, or a path  | *(none)*                 | Your own `:name:` symbols, written inline or kept in a JSON file whose path is given here. **Values are emitted raw** - see the warning below. |

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

### Symbols and emoji

Carve parses `:name:` as a symbol in its core - no extension needed - but what a
name renders as is a render option. Without a map, `:smile:` renders as the text
`:smile:`.

`emoji` turns on a name table. The names are not bundled with this plugin: they
come from `pymdownx.emoji`, which is the same database your site's Markdown
pages resolve `:smile:` through (Material for MkDocs enables it by default). One
source means a `:smile:` in `page.md` and a `:smile:` in `page.crv` cannot drift
apart. If your site configures its own `emoji_index` under `markdown_extensions`
- Material for MkDocs does - that index is used instead, together with the
`options` it is configured with, so a custom icon set resolves on both page
types.

```yaml
plugins:
  - carve:
      emoji: unicode    # the character itself
      # emoji: twemoji  # the <img class="twemoji"> a Markdown page gets
```

`unicode` needs no network and inherits the page font, which on some platforms
has no color emoji face. `twemoji` emits the same element and the same class a
Markdown page gets, so the theme's sizing applies and the two page types look
identical. Install `pymdown-extensions` if your theme does not already pull it
in; a mode other than `none` without it is a configuration error, not a silent
fallback.

`symbols` adds your own entries, layered on top of the emoji table so you can
override one or add something that is not an emoji at all:

```yaml
plugins:
  - carve:
      symbols:
        crv: '<abbr title="Carve">CRV</abbr>'
        rarr: "&rarr;"
```

A long map buries the rest of `mkdocs.yml`, so it can live in a JSON file
instead. The path is resolved relative to `mkdocs.yml`:

```yaml
plugins:
  - carve:
      symbols: symbols.json
```

```json
{
  "crv": "<abbr title=\"Carve\">CRV</abbr>",
  "rarr": "&rarr;"
}
```

The `:name:` match carries a word-boundary guard, so ordinary punctuation is
left alone. With `smile` mapped:

```
A :smile: here     ->  substituted
(:smile:)          ->  substituted
a:smile:b          ->  left literal
3:smile:4          ->  left literal
`:smile:`          ->  left literal (a code span)
ratio 3:4, 12:30   ->  left literal
```

#### The map is trusted input, and it is emitted raw

A mapped value is inserted into the output **without escaping** - the same trust
class as a build-time renderer callback. `symbols: {logo: "<img src='/l.svg'>"}`
emits a real `<img>` element. That is deliberate: processor configuration is
trusted, and it is what makes the `twemoji` mode possible at all.

It is safe only because of where the map can come from. This plugin resolves it
once, in `on_config`, from exactly two places: `mkdocs.yml` itself, and a JSON
file whose path is written in `mkdocs.yml`. No page has been read at that point,
so no page can contribute a value.

**Never build a symbols map out of untrusted or user-supplied input.** Do not
generate the JSON file from page content, from front matter, from a form
submission, or from anything a contributor can influence without review. If a
value can reach the map from outside your own repository, it can put arbitrary
HTML on every page of your site.

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

That install resolves the Carve engine the way a user's install does: anywhere in
the declared range, which today means whatever `carve-lang` PyPI serves as newest.
To reproduce what CI measured instead, install under the same constraints file CI
uses:

```bash
pip install -e .[test] -c constraints-ci.txt
```

The two are deliberately different. `constraints-ci.txt` pins the engine so a
per-PR run states which engine produced its result and a green run stays green;
the daily `Scheduled suite` workflow installs unconstrained, so a new engine
release is noticed there rather than landing unannounced in a pull request. See
the comments in `constraints-ci.txt` for how the pin and the floor in
`pyproject.toml` are raised - they move for different reasons and not together.

The bundled `example/` directory is a complete MkDocs site (Carve homepage,
nested Carve page, a Markdown page, and nav entries) used by the end-to-end
build test. Build it directly with:

```bash
cd example
mkdocs build --strict
```
