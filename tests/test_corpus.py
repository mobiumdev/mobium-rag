from mobium_rag.corpus import MAX_CHARS, section_of, split

MD = """# Challenges

Intro.

### 105. A tap on a button under a dialog reported success

**Found by:** a dialog.

```sh
# not a heading
mobium tap
```

### 106. Not positional

Text.
"""


def test_a_challenges_entry_is_named_by_its_number():
    ids = [p.id for p in split("docs/CHALLENGES.md", MD)]
    assert ids == ["CHALLENGES#challenges", "CHALLENGES#105", "CHALLENGES#106"]


def test_a_heading_inside_code_is_not_a_heading():
    ps = split("docs/CHALLENGES.md", MD)
    assert "# not a heading" in ps[1].text


def test_a_long_section_is_cut_into_parts_of_its_section():
    md = "## Long\n\n" + "\n".join(f"- item {i} " + "x" * 80 for i in range(60))
    ps = split("docs/X.md", md)
    assert len(ps) > 1 and all(len(p.text) <= MAX_CHARS + 50 for p in ps)
    assert {section_of(p.id) for p in ps} == {"docs/X.md#long"}


def test_repeated_headings_get_distinct_ids():
    ps = split("docs/X.md", "## Notes\n\na\n\n## Notes\n\nb\n")
    assert [p.id for p in ps] == ["docs/X.md#notes", "docs/X.md#notes-2"]
