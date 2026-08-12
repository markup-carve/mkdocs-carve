# Releasing

`mkdocs-carve` publishes to PyPI from `.github/workflows/release.yml`, which
runs on a pushed `v*` tag.

## The engine dependency

This plugin renders through `carve-lang`, the Carve engine. That was a git
dependency until 2026-08-12, which also made this package unpublishable: PyPI
refuses a distribution with a direct-URL dependency. `carve-lang` is on PyPI
now, and `pyproject.toml` depends on a version range.

The release workflow still checks for a `@ git+` dependency and fails on one, so
a temporary git pin taken during development cannot reach an upload.

## One-time setup

1. In the repository settings, create an environment named `pypi`. The publish
   job is bound to it, so restricting who may approve it also restricts who may
   release.
2. Give the first release a credential, either way round:
   - **Trusted Publishing, no secret.** On PyPI, add a *pending* publisher for
     the project name `mkdocs-carve`: owner `markup-carve`, repository
     `mkdocs-carve`, workflow `release.yml`, environment `pypi`.
   - **API token.** Set `PYPI_API_TOKEN` as a repository secret. A token for a
     project that does not exist yet has to be account-scoped, because
     project-scoped tokens cannot be minted first. After the first upload, add a
     trusted publisher on the now-existing project and
     `gh secret delete PYPI_API_TOKEN`.

## Per release

1. Move the entries under a version heading in `CHANGELOG.md` and set its date.
2. Set `project.version` in `pyproject.toml`.
3. Tag `vX.Y.Z` and push the tag. The workflow matches `v*` - a bare `0.1.0` tag
   lands but fires nothing.
4. Write the release notes as a draft release on GitHub and publish it.

Before anything is uploaded the build job checks that the tag matches the
packaged version and that no direct-URL dependency survives. Both are failures
you cannot fix after the fact, because PyPI never reuses a version number.
