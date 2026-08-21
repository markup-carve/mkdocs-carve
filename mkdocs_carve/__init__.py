"""mkdocs-carve: render Carve (`.crv`) pages in MkDocs."""

from mkdocs_carve.plugin import CARVE_SUFFIXES, CarvePlugin, convert_carve
from mkdocs_carve.symbols import MODES as EMOJI_MODES

__all__ = ["CarvePlugin", "convert_carve", "CARVE_SUFFIXES", "EMOJI_MODES"]
__version__ = "0.1.0"
