"""mkdocs-carve: render Carve (`.crv`) pages in MkDocs."""

from importlib.metadata import version

from mkdocs_carve.plugin import CARVE_SUFFIXES, CarvePlugin, convert_carve
from mkdocs_carve.symbols import MODES as EMOJI_MODES

__all__ = ["CarvePlugin", "convert_carve", "CARVE_SUFFIXES", "EMOJI_MODES"]
# Read from the installed distribution, so the release gate's check of
# pyproject.toml covers this too.
__version__ = version("mkdocs-carve")
