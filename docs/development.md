# Development

## Setup and maintenance

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
