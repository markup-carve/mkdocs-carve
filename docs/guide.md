# mkdocs-carve guide

## Background

A [MkDocs](https://www.mkdocs.org/) plugin that renders
[Carve](https://github.com/markup-carve) (`.crv`) source files as
documentation pages, converting them to HTML with the
[carve-py](https://github.com/markup-carve/carve-py) engine. Carve pages
are wrapped by your active MkDocs theme exactly like Markdown pages, and they
coexist with `.md` pages in the same `docs/` tree.

## Installation notes

The Carve engine (`carve-lang`, the PyO3 binding over carve-rs) is the
unreleased Carve 0.2 binding on this branch, pinned to a carve-py `next2`
commit. pip builds it from source, so installing needs a Rust toolchain.

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
= Carve in MkDocs

This homepage is written in *Carve* (note: `*bold*` is strong,
`/italic/` is emphasis in Carve).

- lists
- `inline code`
- [links](https://example.com)

|= feature |= works |
| tables   | yes    |
```

## Configuration

| Option       | Type                | Default                  | Description |
|--------------|---------------------|--------------------------|-------------|
| `extensions` | list of names or `{name: options}` | `[]` | Carve 0.2 standard extensions enabled for every Carve page, each with its standard renderer. A 0.1 name is read as its 0.2 counterpart. 0.1 enabled `heading_permalinks` by default; the 0.2 engine has no heading permalinks yet. See [Extensions](#extensions). |
| `raw_html`   | bool                | `false`                  | Emit `=html` blocks and spans verbatim. Carve 0.2 escapes them by default; turn it on only when the site's own authors write every page. |
| `lint`       | bool                | `false`                  | Report lint findings on Carve pages as build warnings, so `mkdocs build --strict` fails on them. See [Lint](#lint). |
| `emoji`      | `none` \| `unicode` \| `twemoji` | `none` | Resolve `:smile:` and friends through the emoji database your Markdown pages already use. See [Symbols and emoji](#symbols-and-emoji). |
| `symbols`    | mapping, or a path  | *(none)*                 | Your own `:name:` symbols, written inline or kept in a JSON file whose path is given here. **Values are emitted raw** - see the warning below. |
| `includes`   | bool                | `false`                  | Expand `{{ path }}` includes for file-backed pages. Off leaves a directive literal. See [Includes](#includes). |
| `include_root` | absolute path     | `docs_dir`               | The containment root includes resolve within. Must be absolute; a relative value is refused, not resolved. |

### Extensions

`extensions` takes the engine's 0.2 standard extension names:

```yaml
plugins:
  - carve:
      extensions:
        - carve.details
        - carve.mathBlock
        - carve.listTable
        - carve.fencedRender.mermaid
```

The names this plugin also accepts from 0.1 map to them, in either spelling
(`math_block` or `math-block`):

| 0.1 name | 0.2 extension |
|---|---|
| `details` | `carve.details` |
| `spoiler` | `carve.spoiler`, `carve.spoilerBlock` |
| `tabs` | `carve.tabs` |
| `code-group` | `carve.codeGroup` |
| `code-callouts` | `carve.codeCallouts` |
| `list-table` | `carve.listTable` |
| `math-block` | `carve.mathBlock` |
| `fenced-render` | `carve.fencedRender.mermaid` |
| `fenced-render-<word>` | `carve.fencedRender.<word>` (`abc`, `chart`, `d2`, `graphviz`, `plantuml`, `vega-lite`, `wavedrom`) |
| `semantic-span` | `carve.semanticSpan` |
| `smart-quotes` | `carve.smartQuotes` |
| `color-swatch` | `carve.colorSwatch` |
| `wikilinks` | `carve.wiki` |
| `citations` | `carve.references` |
| `glossary` | `carve.glossary` |
| `index` | `carve.index` |
| `img-fence` | `carve.imgFence.img`, `carve.imgFence.image` |
| `tab-normalize` | `carve.tabNormalize` |

The 0.2 engine has no `heading-permalinks`, `heading-numbers`,
`heading-level-shift`, `heading-reference`, `table-of-contents`, `toc`,
`external-links` or `autolink` yet
([carve-rs#4476](https://github.com/markup-carve/carve-rs/issues/4476)); naming
one is a configuration error. So is an unknown name.

The extensions reach the page render, the include path and the lint pass. In an
included file, an extension only claims its construct when the including page
uses that extension too ([carve-rs#4481](https://github.com/markup-carve/carve-rs/issues/4481)).

### Extension options

An entry can also be a mapping from an extension name to its options, the same
shape `markdown_extensions` uses. The Carve 0.2 Python binding enables a standard
extension by name only, so options are a configuration error when the build
starts ([carve-py#142](https://github.com/markup-carve/carve-py/issues/142)).

### Lint

Carve's linter reports constructs that parse and render, but not the way the
author meant: a block attribute that attaches to nothing, a reference link with
no definition, a duplicate footnote. Turn it on to see those as build warnings:

```yaml
plugins:
  - carve:
      lint: true
```

```
WARNING -  mkdocs_carve: guide/intro.crv:3:1: unattached-block-attribute: This block attribute reaches no block: ...
```

Each warning names the page, line, column and rule id. `mkdocs build --strict`
treats them like any other warning and fails the build. Without `includes`,
every `{{ path }}` directive is reported as `include-no-resolver`.

With `includes: true` as well, the linter follows the includes and checks every
included Carve file too. A finding inside one names the page and the included
file. The Carve 0.2 diagnostic carries no include chain, so the 0.1
"(included at ...)" suffix is gone:

```
WARNING -  mkdocs_carve: page.crv: parts/frag.crv:3:1: unattached-block-attribute: ...
```

An include that cannot be expanded is reported once, by the include warning
described under [Includes](#includes), not again by the linter.

The linter also reports spellings the canonical writer replaces, and a strict
build fails on them like any other finding, for example
`thematic-break-spelling` for a thematic break written as `---`. `carve fmt`
from the Carve CLI rewrites them.


### Highlighting Carve code blocks

To highlight `carve` fences in your Markdown pages, install
[pygments-carve](https://github.com/markup-carve/pygments-carve). Pygments picks
the lexer up on its own, so no configuration is needed:

```bash
pip install pygments-carve
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

### Includes

A Carve page can pull another file in with `{{ path }}`. The plugin leaves that
literal until a site asks for it:

```yaml
plugins:
  - carve:
      includes: true
```

Paths resolve relative to the file that wrote them, and nothing resolves outside
the containment root. The root is `docs_dir` unless `include_root` names another
one, and an include that would leave it is not expanded.

`include_root` must be an **absolute** path. A relative one is refused rather
than resolved (C2-N-014), because every way of resolving it ends at the directory the build
happened to run from, which is not a root anyone chose. Absolutize it yourself if
you need to - in `mkdocs.yml` that means writing the path out, or setting the
value from your own build script.

```yaml
plugins:
  - carve:
      includes: true
      include_root: /srv/shared/fragments
```

A target that cannot be read is reported as a build warning naming the page and
the cause, and the directive is left as written: `include-not-found`,
`include-outside-root`, `include-cycle` and the other codes of Carve 0.2
(C2-N-061). A directive inside a sentence is text in 0.2 and is never expanded
(C2-N-002).

Select a named region with `@region`. Add `@code:python` when the target is
source code. For example, `index.crv` can contain:

```text
{{ src/example.py @region:demo @code:python }}
{{ parts/intro.crv @region:summary }}
```

Mark the Python region with whole-line `#region demo` and `#endregion` lines.
Mark the Carve region with `%% #region summary` and `%% #endregion` lines.
The marker lines and text outside the region stay out of the page. A missing
or malformed region logs `include-region-invalid`; a file with invalid UTF-8
logs `include-non-text`. Both are build warnings. This plugin renders HTML and
does not format Carve source, so `align_tables` does not apply.

A CSV or TSV file becomes a table when a `{table}` line stands above a code
include of it. `@rows` selects records
and `@cols` picks columns by header name, in the order given:

```text
{table}
{{ plans.csv @code:csv @rows:2-4 @cols:"Price,Plan" }}
```

The header always comes from the top of the file, and `@rows` counts the
header as record 1.

Under `mkdocs serve`, a change anywhere under the containment root triggers a
rebuild, including a fragment that did not exist yet.

Fragments living under `docs_dir` are still pages in their own right, since this
plugin claims every `.crv` file. Keep them out of the built site with MkDocs'
own [`exclude_docs`](https://www.mkdocs.org/user-guide/configuration/#exclude_docs),
or put them under an `include_root` outside `docs_dir`.

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
