from mobium_rag.corpus import Passage
from mobium_rag.graph import _cited, build


def test_cited_reads_lists_and_ranges():
    assert _cited("CHALLENGES 315–317 and defects 55, 61, 63 and 64") == {
        f"CHALLENGES#{n}" for n in (315, 316, 317, 55, 61, 63, 64)}


def test_cited_skips_a_span_of_the_log():
    assert _cited("CHALLENGES 1–300") == set()


def test_links_resolve_relative_and_name_an_entry_by_number():
    ps = [Passage("docs/guides/a.md#x", "docs/guides/a.md", "X", "see [it](../CHALLENGES.md#82-a-switch) and [s](../SETUP.md)"),
          Passage("CHALLENGES#82", "docs/CHALLENGES.md", "82. A switch", "text"),
          Passage("docs/SETUP.md#top", "docs/SETUP.md", "", "setup")]
    assert build(ps)["docs/guides/a.md#x"] == {"CHALLENGES#82", "docs/SETUP.md#top"}
