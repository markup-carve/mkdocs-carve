"""mkdocs-carve: render Carve (`.crv` / `.carve`) pages in MkDocs."""

from mkdocs_carve.plugin import CARVE_SUFFIXES, CarvePlugin, convert_carve

__all__ = ["CarvePlugin", "convert_carve", "CARVE_SUFFIXES"]
__version__ = "0.1.0"
