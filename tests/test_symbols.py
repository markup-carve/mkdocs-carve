"""Tests for the symbol map: what it contains, and what it refuses.

The engine emits a mapped value RAW, so the interesting questions here are not
only "does `:smile:` render" but "can anything other than the site's own
configuration reach the map".
"""

from __future__ import annotations

import pytest

import carve
from mkdocs_carve.symbols import MODES, SymbolError, build, emoji_map

# A stand-in for `pymdownx.emoji.twemoji`: same call shape, same three keys,
# small enough to assert on exactly. Passing it in is what lets these tests
# describe the mapping rules rather than the contents of a 3840-entry table.
def _index(_options, _md):
    return {
        "name": "test",
        "emoji": {
            ":smile:": {"unicode": "1f604"},
            ":thumbsup:": {"unicode": "1f44d"},
            # An icon rather than an emoji: no codepoint, resolves to an SVG
            # file on disk. Must not land in the map.
            ":material-home:": {"path": "home.svg"},
        },
        "aliases": {":+1:": ":thumbsup:", ":dangling:": ":not-there:"},
    }


def _empty_index(_options, _md):
    return {"name": "empty", "emoji": {}, "aliases": {}}


# --- 1. modes ---------------------------------------------------------------


def test_none_is_an_empty_map():
    assert emoji_map("none", _index) == {}


def test_unicode_mode_maps_a_bare_name_to_the_character():
    assert emoji_map("unicode", _index)["smile"] == "\U0001f604"


def test_twemoji_mode_matches_the_element_a_markdown_page_gets():
    value = emoji_map("twemoji", _index)["smile"]
    assert 'class="twemoji"' in value
    assert value.endswith('title=":smile:" />')
    assert "1f604.svg" in value


def test_an_unknown_mode_is_refused():
    with pytest.raises(SymbolError, match="unknown emoji mode"):
        emoji_map("emojione", _index)


def test_modes_are_the_three_documented_ones():
    assert MODES == ("none", "unicode", "twemoji")


# --- 2. what the table does and does not carry ------------------------------


def test_an_alias_resolves_through_to_its_target():
    """`pymdownx` renders `:+1:` on a Markdown page; a Carve page must too."""
    table = emoji_map("unicode", _index)
    assert table["+1"] == table["thumbsup"] == "\U0001f44d"


def test_a_dangling_alias_is_dropped_rather_than_raising():
    assert "dangling" not in emoji_map("unicode", _index)


def test_an_icon_without_a_codepoint_is_left_out():
    """It would need a file read per entry, and a literal is visibly missing."""
    assert "material-home" not in emoji_map("unicode", _index)


def test_a_mode_with_no_database_behind_it_is_a_named_error():
    with pytest.raises(SymbolError, match="pymdown-extensions"):
        emoji_map("unicode", _empty_index)


# --- 3. build(): the site's own entries win ---------------------------------


def test_the_sites_own_entry_overrides_an_emoji_of_the_same_name():
    table = build("unicode", {"smile": "SMILE"}, _index)
    assert table["smile"] == "SMILE"


def test_nothing_to_pass_is_none_not_an_empty_map():
    """`None` leaves the engine's default alone; `{}` would say "no symbols"."""
    assert build("none", None, _index) is None
    assert build("none", {}, _index) is None


def test_site_entries_alone_need_no_emoji_database():
    assert build("none", {"a": "b"}, _index) == {"a": "b"}


# --- 4. the map reaches the engine and behaves ------------------------------


def test_a_mapped_symbol_renders_and_an_unmapped_one_stays_literal():
    html = carve.to_html("A :smile: but not :nope:", symbols=build("unicode", None, _index))
    assert "\U0001f604" in html
    assert ":nope:" in html


@pytest.mark.parametrize(
    "source,substituted",
    [
        ("A :smile: here", True),
        ("(:smile:)", True),
        ("x :smile:, y", True),
        # The word-boundary guard is the engine's, and it has to keep holding:
        # a map that fired inside a word would rewrite ratios and timestamps.
        ("a:smile:b", False),
        ("3:smile:4", False),
        ("`:smile:`", False),
        ("ratio 3:4 and time 12:30", False),
    ],
)
def test_the_word_boundary_guard_still_holds(source, substituted):
    html = carve.to_html(source, symbols={"smile": "SUBSTITUTED"})
    assert ("SUBSTITUTED" in html) is substituted


def test_a_mapped_value_is_emitted_raw():
    """Not an accident, and not something to "fix" - it is the contract.

    carve-lang's own ``to_html`` docstring: "a mapped symbol value is inserted
    as TRUSTED RAW output ... NEVER build a symbols map out of untrusted /
    user-supplied input." This test exists so that if the engine ever started
    escaping, the change is noticed here rather than by a site whose symbols
    silently turned into visible markup.
    """
    html = carve.to_html(":logo: x", symbols={"logo": "<img src='/l.svg'>"})
    assert "<img src='/l.svg'>" in html
    assert "&lt;img" not in html


# --- 5. The index factory is called the way pymdownx calls it ---------------


def test_the_sites_index_options_reach_the_factory():
    """`pymdownx` calls `index(config["options"], md)`; Material reads them.

    Dropping the options silently builds a different table than the Markdown
    pages on the same site get, which is exactly the drift this module exists
    to prevent.
    """
    seen = {}

    def recording_index(options, _md):
        seen["options"] = options
        return {"name": "r", "emoji": {":x:": {"unicode": "1f604"}}, "aliases": {}}

    emoji_map("unicode", recording_index, {"custom_icons": ["overrides/.icons"]})
    assert seen["options"] == {"custom_icons": ["overrides/.icons"]}


def test_two_option_sets_do_not_share_one_cached_table():
    def index(options, _md):
        point = "1f604" if options.get("set") == "a" else "1f44d"
        return {"name": "v", "emoji": {":x:": {"unicode": point}}, "aliases": {}}

    assert emoji_map("unicode", index, {"set": "a"})["x"] == "\U0001f604"
    assert emoji_map("unicode", index, {"set": "b"})["x"] == "\U0001f44d"


def test_a_legacy_zero_argument_index_is_still_called():
    """`pymdownx` still supports (and deprecation-warns about) this form."""

    def legacy():
        return {"name": "l", "emoji": {":x:": {"unicode": "1f604"}}, "aliases": {}}

    assert emoji_map("unicode", legacy)["x"] == "\U0001f604"


def test_editing_the_returned_map_does_not_edit_the_cached_one():
    first = emoji_map("unicode", _index)
    first["smile"] = "MUTATED"
    assert emoji_map("unicode", _index)["smile"] == "\U0001f604"
